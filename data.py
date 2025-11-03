# In your data.py
import numpy as np
import pandas as pd
import sqlite3
from sklearn.ensemble import IsolationForest

def create_and_analyze_db():
    np.random.seed(42)
    # --- 1. Create the DataFrames ---
    # 'Hobbyist' segment: low value, but high rate of weird anomalies
    users_hobby = pd.DataFrame({'user_id': range(1, 501), 'segment': 'Hobbyist'})
    tx_hobby_normal = pd.DataFrame({
        'user_id': np.random.choice(users_hobby['user_id'], 1000),
        'amount': np.random.normal(loc=50, scale=10, size=1000),
        'hour': np.random.normal(loc=18, scale=4, size=1000)
    })
    # 20 anomalies (tiny amounts at odd hours)
    tx_hobby_anomalies = pd.DataFrame({
        'user_id': np.random.choice(users_hobby['user_id'], 20),
        'amount': np.random.normal(loc=1, scale=0.5, size=20),
        'hour': np.random.normal(loc=3, scale=1, size=20)
    })

    # 'Enterprise' segment: high value, but very few anomalies
    users_enterprise = pd.DataFrame({'user_id': range(501, 551), 'segment': 'Enterprise'})
    tx_enterprise_normal = pd.DataFrame({
        'user_id': np.random.choice(users_enterprise['user_id'], 500),
        'amount': np.random.normal(loc=5000, scale=1000, size=500),
        'hour': np.random.normal(loc=11, scale=2, size=500)
    })
    # 2 anomalies (massive amounts)
    tx_enterprise_anomalies = pd.DataFrame({
        'user_id': np.random.choice(users_enterprise['user_id'], 2),
        'amount': [50000, 75000],
        'hour': [10, 14]
    })
    
    # Combine all data
    users_df = pd.concat([users_hobby, users_enterprise], ignore_index=True)
    tx_df = pd.concat([tx_hobby_normal, tx_hobby_anomalies, tx_enterprise_normal, tx_enterprise_anomalies], ignore_index=True).sample(frac=1)

    # --- 2. Create the SQLite DB File ---
    conn = sqlite3.connect('analytics.db')
    users_df.to_sql('users', conn, if_exists='replace', index=False)
    tx_df.to_sql('transactions', conn, if_exists='replace', index=False)
    conn.close()
    print("analytics.db file created successfully.")

    # --- 3. Ground Truth Analysis (This is what the AI must do) ---
    print("\n--- Ground Truth Analysis Start ---")
    
    # This is the query the AI *should* run
    query = """
    SELECT t.amount, t.hour, u.segment
    FROM transactions t
    JOIN users u ON t.user_id = u.user_id
    """
    conn = sqlite3.connect('analytics.db')
    full_data = pd.read_sql_query(query, conn)
    conn.close()

    anomaly_rates = {}
    for segment in full_data['segment'].unique():
        sub_df = full_data[full_data['segment'] == segment][['amount', 'hour']]
        
        # Use a standard Isolation Forest
        iso_forest = IsolationForest(contamination='auto', random_state=42)
        predictions = iso_forest.fit_predict(sub_df)
        n_anomalies = np.sum(predictions == -1)
        rate = n_anomalies / len(sub_df)
        
        print(f"  Analysis for '{segment}': Found {n_anomalies} anomalies. Rate: {rate:.4f}")
        anomaly_rates[segment] = rate

    winner = max(anomaly_rates, key=anomaly_rates.get)
    print(f"\n--- Final Result ---")
    print(f"The segment with the highest *rate* of anomalies is: '{winner}'")
    return winner

create_and_analyze_db()
