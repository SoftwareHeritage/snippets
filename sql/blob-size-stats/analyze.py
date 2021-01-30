#!/usr/bin/env python3

import pandas as pd

DATA_FILE = "blob-size-stats.csv"

df = pd.read_csv(DATA_FILE, low_memory=False, skiprows=1, names=["blob size"])
print(df.describe())
