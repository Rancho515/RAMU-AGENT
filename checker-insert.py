import mysql.connector

# Database connection
conn = mysql.connector.connect(
    host="208.91.199.36",
    user="igssewjk_Iiot",
    password="Sgi@admin",
    database="igssewjk_Gggg"
)

cursor = conn.cursor()

# Data to insert
credential_id = "agent001"
credential_password = "pass123"
assigned_number = "+919876543210"
sip_user = "sip_agent001"
sip_pass = "sip_password"

# Insert query
query = """
INSERT INTO agent_checker 
(credential_id, credential_password, assigned_number, sip_user, sip_pass)
VALUES (%s, %s, %s, %s, %s)
"""

values = (
    credential_id,
    credential_password,
    assigned_number,
    sip_user,
    sip_pass
)

cursor.execute(query, values)

conn.commit()

print("Data inserted successfully!")

cursor.close()
conn.close()
