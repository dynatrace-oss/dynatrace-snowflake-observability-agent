--
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
--
--
--
-- APP.F_OBFUSCATE_QUERY_TEXT(TEXT, MODE) applies query text obfuscation based on the configured mode.
--
-- Modes:
--   'off'      - return text unchanged (default behavior)
--   'literals' - replace single-quoted string literals and standalone numeric literals with '?' placeholders;
--                SQL structure, keywords, table/column names are preserved
--   'full'     - replace the entire text with '[OBFUSCATED]'
--   <other>    - treated as 'off' (safe fallback)
--
-- Note: 'literals' mode uses best-effort regex replacement. It may not handle all edge cases
-- (e.g. dollar-quoted strings, escaped quotes). It is not a security boundary, but reduces
-- accidental exposure of credentials and PII in observability data.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace function APP.F_OBFUSCATE_QUERY_TEXT(TEXT varchar, MODE varchar)
returns varchar
language sql
as
$$
    case
        when MODE = 'full'
            then '[OBFUSCATED]'
        when MODE = 'literals'
            then regexp_replace(
                    regexp_replace(TEXT, '''[^'']*''', '''?'''),
                    '\\b[0-9]+\\.?[0-9]*\\b',
                    '?'
                 )
        else TEXT
    end
$$;

grant usage on function APP.F_OBFUSCATE_QUERY_TEXT(varchar, varchar) to role DTAGENT_VIEWER;
