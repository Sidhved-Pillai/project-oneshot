from io import BytesIO
from pathlib import Path
import os
import pandas as pd


def workbook_bytes(df):
    output = BytesIO(); df.to_excel(output, index=False); return output.getvalue()


def save_master_safely(df, path, text_columns=()):
    path = Path(path)
    clean = df.copy()
    for col in text_columns:
        if col in clean: clean[col] = clean[col].fillna("").astype(str)
    temp = path.with_suffix(".saving.xlsx")
    clean.to_excel(temp, index=False)
    os.replace(temp, path)

