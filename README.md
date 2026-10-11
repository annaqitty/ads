# Multi-Source Ad Intelligence Scraper

Collect publicly accessible advertising data from multiple ad-discovery
platforms using a keyword and country filter. The script combines
results into timestamped CSV-compatible text files and continues running
when an individual source fails.

> **Important:** This project is an experimental scraper, not an
> official API integration. Website layouts, endpoints, access controls,
> and terms can change. Some sources may return incomplete data or no
> results. Traffic, impressions, CTR, CPC, and commission values are
> only populated when a source exposes them.

## Features

-   **Multi-source collection** from Meta Ads Library, TikTok Creative
    Center, Google Ads Transparency Center, BigSpy, Dropispy, and IXSPY.
-   **Keyword-based search** with configurable country code.
-   **Fault isolation:** a failure in one source is logged and does not
    stop the remaining source functions.
-   **Configurable target limit** for rows collected per source.
-   **Standardized output schema** across collected ad records.
-   **Timestamped output files** organized in an `output/` directory.
-   **Advertiser summary and ad-text ranking** outputs.
-   **Indonesia time zone** (`Asia/Jakarta`) for output timestamps.

## Data sources

  -----------------------------------------------------------------------
  Source                              Intended data
  ----------------------------------- -----------------------------------
  Meta Ads Library                    Advertiser/page, ad text, start
                                      date, ad link, status

  TikTok Creative Center              Brand, ad title, first-shown date,
                                      impressions, CTR, reach/traffic,
                                      link

  Google Ads Transparency Center      Advertiser label and transparency
                                      link

  BigSpy                              Ad details and any
                                      traffic/commission fields exposed
                                      by the page

  Dropispy                            Ad details and any
                                      traffic/commission fields exposed
                                      by the page

  IXSPY                               Ad details and any
                                      traffic/commission/CPC fields
                                      exposed by the page
  -----------------------------------------------------------------------

The fields available depend on each source. Blank fields mean the
scraper did not obtain a value; they do **not** mean the value is zero.
Data returned by third-party websites may be delayed, estimated,
restricted, or unavailable.

## Requirements

-   Python 3.10 or newer recommended
-   Internet connection
-   Chromium support for Playwright browser-based sources

## Installation

Clone the repository and enter its directory:

``` bash
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
```

Create and activate a virtual environment (recommended):

**Windows**

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

``` bash
python -m pip install requests beautifulsoup4 playwright
python -m playwright install chromium
```

## Configuration

The script reads these environment variables:

  -----------------------------------------------------------------------
  Variable                Default                 Description
  ----------------------- ----------------------- -----------------------
  `KEYWORD`               `shopee`                Search keyword and
                                                  basis for the output
                                                  filename

  `COUNTRY`               `ID`                    Country/region code
                                                  passed to supported
                                                  sources

  `TARGET`                `500`                   Maximum number of rows
                                                  retained per source
  -----------------------------------------------------------------------

### Windows PowerShell

``` powershell
$env:KEYWORD = "shopee"
$env:COUNTRY = "ID"
$env:TARGET = "500"
python main.py
```

### Windows Command Prompt

``` bat
set KEYWORD=shopee
set COUNTRY=ID
set TARGET=500
python main.py
```

### Linux / macOS

``` bash
KEYWORD="shopee" COUNTRY="ID" TARGET="500" python main.py
```

Replace `main.py` with the actual Python filename in your repository.
Environment variables set in a shell apply to that shell session.

## Usage

Run the script:

``` bash
python main.py
```

The program attempts each configured source in sequence, logs the number
of rows returned or an error, combines the collected rows, and writes
results under `output/`.

## Output files

Files are named using the sanitized keyword label and a timestamp in the
`Asia/Jakarta` time zone. Example names for the keyword `shopee`:

``` text
output/
├── shopee-Ads_(2026-10-12_10-30-00).txt
├── shopee-Top-Advertiser_(2026-10-12_10-30-00).txt
└── shopee-Top-Ads_(2026-10-12_10-30-00).txt
```

The date and time above are examples; actual filenames use the time when
the script runs. The files use CSV formatting and UTF-8 with a
byte-order mark, despite the `.txt` extension, so they can be opened by
many spreadsheet applications. Import them as CSV if your application
does not automatically detect the format.

### Ads file columns

  Column              Meaning
  ------------------- ------------------------------------------------
  `keyword`           Configured search keyword
  `advertiser`        Advertiser or brand name, when available
  `ad_text`           Ad copy or title, when available
  `started`           Start/first-shown date, when available
  `platform`          Source/platform identifier
  `status`            Status label assigned by the scraper
  `traffic`           Traffic/reach value, if exposed by the source
  `commission_rate`   Commission value, if exposed by the source
  `cpc`               Cost-per-click value, if exposed by the source
  `ctr`               Click-through rate, if exposed by the source
  `impressions`       Impression count, if exposed by the source
  `link`              Ad, advertiser, or landing-page link

The `Top-Advertiser` output is intended to summarize advertisers by
collected ad count and source. The `Top-Ads` output is intended to rank
collected records by the length of their ad text. Validate these summary
files against your run logs before relying on them for analysis.

## Reliability and limitations

-   The scraper uses a mixture of HTTP requests and browser automation.
    A source may change its HTML, endpoint, response format, or access
    policy at any time.
-   Some sites may require JavaScript, authentication, cookies, or other
    access conditions that this script does not handle.
-   The `status` value is assigned by the script for collected records;
    it should not be treated as independent verification of a live ad.
-   The `TARGET` setting limits rows per source function, not the total
    number of combined rows.
-   Results from different platforms may overlap and are not
    automatically deduplicated.
-   Traffic and advertising metrics are not guaranteed to be available
    or comparable across platforms.
-   A source failure is logged and skipped, but a run with no collected
    data does not produce the normal set of result files.
-   Review the current source code and test outputs before using the
    generated data for business decisions.

## Responsible use

Use this project only in ways permitted by the relevant websites and
applicable laws. Respect rate limits, robots/access policies where
applicable, privacy requirements, and platform terms. Do not use
collected data to harass people, bypass access controls, or misrepresent
estimates as verified facts.

## Troubleshooting

**A source returns zero rows** - Check whether the source is reachable
and currently exposes the searched data. - Try a different keyword or
country code. - Inspect the source's error output and confirm the
website has not changed.

**Playwright sources fail** - Install the browser binary with
`python -m playwright install chromium`. - Confirm that Chromium can
launch in your environment. - Check whether the target site requires a
login or blocks automated access.

**Some columns are blank** - Not every source provides every metric.
Blank fields are expected when a value is unavailable.

**No output files contain data** - Review the per-source logs. The
script exits before saving the normal output set if all sources return
no rows.

## Contributing

Issues and pull requests are welcome. Please include reproducible steps,
relevant error messages, and the source/platform affected. Avoid
publishing credentials, session cookies, or personal data in bug
reports.

## Disclaimer

This project is provided for educational and research purposes. It is
not affiliated with or endorsed by Meta, TikTok, Google, BigSpy,
Dropispy, or IXSPY. Use is at your own risk. No guarantee is made
regarding data accuracy, completeness, availability, or fitness for a
particular purpose.

## License

Add a `LICENSE` file before claiming a specific open-source license.
Until then, the repository's license terms are unspecified.
