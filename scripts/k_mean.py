import os
import warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

try:
    import joblib.externals.loky.backend.context as _loky_ctx
    _loky_ctx._count_physical_cores = lambda: (os.cpu_count() or 4, None)
except Exception:
    pass

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# 1. Load data CSV
df = pd.read_csv("kaggle/release/v1.0.3/cleaning_decisions.csv")

# Filter hanya produk laptop valid (buang aksesoris seperti charger/tas)
if "eligibility_decision" in df.columns:
    df = df[df["eligibility_decision"] == "VALID_LAPTOP"]

# Tentukan fitur yang akan dipakai untuk clustering
features = [
    "price",
    "rating",
    "review_count_resolved"
]

# 2. Cek baris yang mengandung nilai null
print("Jumlah baris awal:", len(df))
print("\nJumlah null per kolom:")
print(df[features].isnull().sum())

# Tampilkan contoh baris yang ada null-nya (menggunakan axis=1)
rows_miss = df[df[features].isnull().any(axis=1)]
print(f"\nTotal baris yang ada null: {len(rows_miss)}")
print(rows_miss[features].head())

# 3. Pembersihan: buang baris yang memiliki nilai null pada kolom fitur
df = df.dropna(subset=features).reset_index(drop=True)
print("\nJumlah baris setelah dibersihkan (dropna):", len(df))

# 4. Ambil fitur dan lakukan standarisasi (scaling)
X = df[features]
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 5. Model K-Means clustering
kmeans = KMeans(
    n_clusters=3,
    random_state=42,
    n_init="auto"
)

# Tambahkan label cluster ke dataframe
df["cluster"] = kmeans.fit_predict(X_scaled)

# 6. Tampilkan ringkasan hasil
print("\nJumlah data per cluster:")
print(df["cluster"].value_counts())

print("\nContoh hasil data setelah clustering:")
print(df[["product_name", "price", "rating", "review_count_resolved", "cluster"]].head())

# Simpan ke CSV baru
output_file = "kaggle/release/v1.0.3/clustered_laptops.csv"
df.to_csv(output_file, index=False)
print(f"\nData berhasil disimpan ke: {output_file}")
