"""Mechanisms allowing for parsing and sending spans"""

##region ------------------------------ IMPORTS  -----------------------------------------
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
from typing import Optional, Any, Tuple, Dict, List, Callable, Generator
from snowflake import snowpark
from opentelemetry.trace import SpanKind, INVALID_SPAN_ID, INVALID_TRACE_ID
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, Tracer
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager
from dtagent.otel import USER_AGENT


##endregion COMPILE_REMOVE

##region ------------------------ OpenTelemetry SPANS ---------------------------------


class ExistingIdGenerator(RandomIdGenerator):
    """This generator can retrieve span and trace id from a given telemetry row.
    If that happens, the values are turned into int values and recorded until they are accessed for the first time;
    after access, they are set to None.
    If they are None, the implementation from RandomIdGenerator is used instead.
    """

    def __init__(self):
        """Initializes generator with an empty span and trace ids -> this will make sure generator will fallback to super() implementation"""
        super().__init__()

        self.span_id = None
        self.trace_id = None

    def set_span_row(self, d_span: Dict[str, Any]) -> None:
        """Sets internal span and trace ids to those found in given data row, if any provided

        Args:
            d_span (Dict[str, Any]): data row which needs to have _SPAN_ID and _TRACE_ID columns with int values
        """
        from dtagent import LOG  # COMPILE_REMOVE

        if d_span.get("_SPAN_ID"):
            try:
                self.span_id = int(d_span["_SPAN_ID"], 16)
            except (TypeError, ValueError):
                self.span_id = None
                LOG.debug("Invalid span_id: %s", d_span["_SPAN_ID"])

        if d_span.get("_TRACE_ID"):
            try:
                self.trace_id = int(d_span["_TRACE_ID"], 16)
            except (TypeError, ValueError):
                self.trace_id = None
                LOG.debug("Invalid trace_id: %s", d_span["_TRACE_ID"])

    def generate_span_id(self) -> int:
        span_id = super().generate_span_id() if self.span_id is None or self.span_id == INVALID_SPAN_ID else self.span_id

        self.span_id = None
        return span_id

    def generate_trace_id(self) -> int:
        trace_id = super().generate_trace_id() if self.trace_id is None or self.trace_id == INVALID_TRACE_ID else self.trace_id

        self.trace_id = None
        return trace_id


class Spans:
    """Main Spans class"""

    from dtagent.config import Configuration  # COMPILE_REMOVE

    SPAN_KIND_MAP = {
        "SPAN_KIND_INTERNAL": SpanKind.INTERNAL,
        "SPAN_KIND_SERVER": SpanKind.SERVER,
        "SPAN_KIND_CLIENT": SpanKind.CLIENT,
        "SPAN_KIND_PRODUCER": SpanKind.PRODUCER,
        "SPAN_KIND_CONSUMER": SpanKind.CONSUMER,
    }

    def __init__(self, resource: Resource, configuration: Configuration):
        """Initializes tracers."""

        self._otel_tracer: Optional[Tracer] = None
        self._otel_id_generator: Optional[ExistingIdGenerator] = None
        self._otel_tracer_provider: Optional[TracerProvider] = None
        self._configuration = configuration

        self._setup_tracer(resource)

    def _get_span_kind(self, d_span: Dict[str, Any], is_top_level: bool) -> SpanKind:
        """Returns span kinds object based on either the _SPAN_KIND column in data or checking whether the span is the top level one"""
        return Spans.SPAN_KIND_MAP.get(d_span.get("_SPAN_KIND")) or (SpanKind.SERVER if is_top_level else SpanKind.INTERNAL)

    def _setup_tracer(self, resource: Resource) -> None:
        """
        Sets up OTLP Trace for sending spans to Dynatrace
        """
        from opentelemetry.sdk.trace import SpanLimits
        from opentelemetry import trace
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        class CustomUserAgentOTLPSpanExporter(OTLPSpanExporter):
            """Custom OTLP Span Exporter that sets a custom User-Agent header."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._session.headers["User-Agent"] = USER_AGENT

        exporter = CustomUserAgentOTLPSpanExporter(
            endpoint=f'{self._configuration.get("otlp.http")}/v1/traces',
            headers={"Authorization": f'Api-Token {self._configuration.get("dt.token")}'},
            session=CustomLoggingSession(),
        )

        self._otel_id_generator = ExistingIdGenerator()
        self._otel_tracer_provider = TracerProvider(
            resource=resource,
            id_generator=self._otel_id_generator,
            span_limits=SpanLimits(
                max_events=self._configuration.get(otel_module="spans", key="max_event_count", default_value=2000),
                max_event_attributes=self._configuration.get(otel_module="spans", key="max_attributes_per_event_count", default_value=250),
                max_span_attributes=self._configuration.get(otel_module="spans", key="max_span_attributes", default_value=250),
            ),
        )

        self._otel_tracer_provider.add_span_processor(
            BatchSpanProcessor(
                span_exporter=exporter,
                export_timeout_millis=self._configuration.get(otel_module="spans", key="export_timeout_millis", default_value=10000),
                max_export_batch_size=self._configuration.get(otel_module="spans", key="max_export_batch_size", default_value=100),
            )
        )
        trace.set_tracer_provider(self._otel_tracer_provider)
        self._otel_tracer = trace.get_tracer(
            self._configuration.get("resource.attributes").get("telemetry.exporter.name").lower() + ".otel.traces"
        )

    def _get_sub_rows(
        self,
        session: snowpark.Session,
        view_name: str,
        parent_row_id_col: str,
        row_id: str,
    ) -> Generator[Dict, None, None]:
        """Returns sub_rows for specified row_id searching for it in parent_row_id_col within a specified view."""

        from snowflake.snowpark.functions import col

        df_sub_rows = session.table(view_name).filter(col(parent_row_id_col) == row_id)

        for row in df_sub_rows.collect():
            row_dict = row.as_dict(recursive=True)

            yield row_dict

    def generate_span(
        self,
        d_span: Dict[str, Any],
        session: snowpark.Session,
        row_id_col: str,
        parent_row_id_col: str,
        *,
        view_name: str,
        f_span_events: Optional[Callable[[Dict[str, Any]], Tuple[List[Dict[str, Any]], int]]] = None,
        f_log_events: Optional[Callable[[Dict[str, Any]], None]] = None,
        context: Optional[Dict] = None,
        is_top_level: bool = False,
    ) -> int:
        """
        Sends aggregated query history row as a OTLP span

        Return:
            int     Number of span events generated
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE
        from dtagent.util import _adjust_timestamp, _unpack_json_dict  # COMPILE_REMOVE
        from dtagent.util import _cleanup_dict, _pack_values_to_json_strings  # COMPILE_REMOVE
        from opentelemetry.sdk.trace import StatusCode

        def __process_subrows(row_id: str):
            """Generates sub-spans for specified row_id"""

            LOG.log(LL_TRACE, "- will process sub-spans -")

            span_events_added = 0
            for row_dict in self._get_sub_rows(session, view_name, parent_row_id_col, row_id):
                LOG.log(LL_TRACE, "Will generate sub-span for %s", row_dict[row_id_col])
                span_events_added += self.generate_span(
                    row_dict,
                    session,
                    row_id_col,
                    parent_row_id_col,
                    view_name=view_name,
                    f_span_events=f_span_events,
                    f_log_events=f_log_events,
                    context=context,
                )

            LOG.log(LL_TRACE, "- have processed sub-spans -")
            return span_events_added

        events_added = 0
        events_failed = 0
        subspan_events_added = 0

        _adjust_timestamp(d_span)

        span_attributes = _pack_values_to_json_strings(
            _cleanup_dict(
                _unpack_json_dict(d_span, ["DIMENSIONS", "ATTRIBUTES", "METRICS"]) | (context or {})
            )  # context is Dynatrace Snowflake Observability Agent context, not a span one
        )

        self._otel_id_generator.set_span_row(d_span)

        with self._otel_tracer.start_as_current_span(
            name=d_span["NAME"],
            start_time=int(d_span["START_TIME"]),
            end_on_exit=False,
            attributes=span_attributes,
            kind=self._get_span_kind(d_span, is_top_level),
        ) as current_span:

            row_id = d_span.get(row_id_col, None)
            LOG.log(LL_TRACE, "Processing span for row_id = %r at start_time=%r", row_id, d_span["START_TIME"])

            if row_id and f_span_events:
                span_events, events_failed = f_span_events(d_span)
                for span_event in span_events:
                    try:
                        current_span.add_event(**span_event)
                        LOG.log(LL_TRACE, "Event for row id = %r: %r", row_id, span_event)
                    except TypeError as e:
                        events_failed += 1
                        raise TypeError(f"row_id = {d_span[row_id_col]}; event = {span_event}; e = {e}") from e
                events_added = len(span_events)

            current_span.set_attribute("dsoa.debug.span.events.added", events_added)
            current_span.set_attribute("dsoa.debug.span.events.failed", events_failed)

            LOG.log(
                LL_TRACE,
                "dsoa.debug.span.events.added[%r]: %d",
                row_id,
                events_added,
            )

            if f_log_events:
                f_log_events(d_span)

            subspan_events_added = __process_subrows(row_id) if d_span.get("IS_PARENT", False) else 0

            current_span.set_status(StatusCode[d_span.get("STATUS_CODE", "UNSET")])
            current_span.end(int(d_span["END_TIME"]))

        LOG.log(LL_TRACE, "Leaving span reporting for %r", row_id)
        OtelManager.verify_communication()

        return subspan_events_added + events_added

    def flush_traces(self) -> bool:
        """Force flushes the cached traces."""

        if self._otel_tracer_provider:
            return self._otel_tracer_provider.force_flush()

        return False

    def shutdown_tracer(self) -> None:
        """Sends remaining traces and shuts down the tracer."""

        if self._otel_tracer_provider:
            self._otel_tracer_provider.force_flush()
            self._otel_tracer_provider.shutdown()


##endregion
