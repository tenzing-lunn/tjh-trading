"""Download Fama-French factor data from Ken French Data Library.

Run LOCALLY (needs internet):
    python3 fetch_french.py

Downloads two monthly series from Ken French's public data library and saves as clean CSVs
in research_data/french/ (gitignored, like realdata/). Parses only the first monthly block
from each file (until blank line or non-numeric date).

Dependencies: pandas (already in requirements).
"""
import os
import urllib.request
import zipfile
import io
import pandas as pd


def fetch_and_parse_french_data(url, output_path, series_name):
    """Download a zip from Ken French's library, extract and parse the monthly CSV block.

    Args:
        url: Direct URL to the .zip file (contains one CSV)
        output_path: Where to save the clean CSV
        series_name: Human name for logging

    Saves a CSV with columns [date, ...values...], date format YYYY-MM.
    """
    print(f"Fetching {series_name}...", end=" ", flush=True)

    # Download zip
    with urllib.request.urlopen(url) as response:
        zip_data = response.read()

    # Extract CSV from zip
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        # Assume one CSV file in the zip
        csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
        if not csv_files:
            raise ValueError(f"No CSV found in zip from {url}")
        csv_name = csv_files[0]
        csv_content = zf.read(csv_name).decode('utf-8')

    # Parse the CSV, skipping preamble lines until we hit the header (contains column names)
    lines = csv_content.strip().split('\n')

    # Find the header line (short line with commas, like ",Mom" or similar)
    # The header is typically a short line with just column names, not a sentence
    start_idx = None
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Header line: has comma, is short (< 100 chars), and doesn't end with period
        # Typically looks like ",Mom" or "Date,Mom,Value"
        if ',' in line and len(line_stripped) < 100 and not line_stripped.rstrip().endswith('.'):
            # Double-check it's not a preamble sentence by checking if it's mostly alphabetic before the comma
            first_part = line_stripped.split(',')[0]
            # If first part is very long or contains spaces after first word, it's likely a sentence
            if len(first_part) < 30 and (not first_part or first_part.isidentifier() or first_part[0].isdigit()):
                start_idx = i
                break

    if start_idx is None:
        raise ValueError(f"Could not find header line in {series_name}")

    # Extract header
    header_line = lines[start_idx].strip().split(',')
    header = [h.strip() for h in header_line]

    # Collect data rows (start from the line after header)
    # Stop when we hit a line that doesn't start with a 6-digit date
    data_lines = []
    for i in range(start_idx + 1, len(lines)):
        line = lines[i].strip()
        if not line:  # Blank line marks end of monthly block
            break

        parts = line.split(',')
        if not parts[0].strip():  # Empty first column
            continue

        # Check if first column is a valid date (YYYYMM format, 6 digits)
        first_col = parts[0].strip()
        if not (first_col.isdigit() and len(first_col) == 6):
            # Non-numeric date, end of monthly block
            break

        data_lines.append(parts)

    # Build dataframe
    if not data_lines:
        raise ValueError(f"No data rows found in {series_name}")

    # Convert date YYYYMM -> YYYY-MM for proper pandas round-trip
    dates = [f"{line[0].strip()[:4]}-{line[0].strip()[4:6]}" for line in data_lines]

    # Construct dataframe from header + data
    df_dict = {}
    df_dict['date'] = dates

    # Process each column (skip first which is date)
    for col_idx in range(1, len(header)):
        col_name = header[col_idx].strip()
        if not col_name:  # Skip empty headers
            continue

        # Collect values, convert to float
        values = []
        for line in data_lines:
            val_str = line[col_idx].strip() if col_idx < len(line) else ""
            try:
                values.append(float(val_str))
            except (ValueError, IndexError):
                values.append(None)
        df_dict[col_name] = values

    df = pd.DataFrame(df_dict)

    # Ensure date column is datetime
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Save to CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"saved ({len(df)} rows, {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')})")
    return df


def main():
    """Download and parse both Fama-French factor files."""

    # URLs confirmed reachable
    momentum_url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
    portfolios_url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/10_Portfolios_Prior_12_2_CSV.zip"

    momentum_output = "research_data/french/momentum_factor_monthly.csv"
    portfolios_output = "research_data/french/10_portfolios_momentum_monthly.csv"

    try:
        fetch_and_parse_french_data(momentum_url, momentum_output, "Momentum Factor")
        fetch_and_parse_french_data(portfolios_url, portfolios_output, "10 Portfolios (Momentum)")
        print("\nDone. Data saved to research_data/french/")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
