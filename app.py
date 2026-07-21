import os
os.environ['CASSANDRA_DRIVER_NO_EXTENSIONS'] = '1'

import streamlit as st
from datetime import datetime
import pandas as pd

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

st.set_page_config(
    page_title="Notifications Cassandra", 
    page_icon="🔔",
    layout="wide"
)

# --- Fonction de connexion à Astra DB ---
@st.cache_resource
def get_cassandra_session():
    try:
        # Configuration cloud avec le Secure Connect Bundle (.zip)
        cloud_config = {
            'secure_connect_bundle': 'secure-connect-notification-db.zip'  # Nom exact de ton fichier .zip
        }
        auth_provider = PlainTextAuthProvider(
            st.secrets["ASTRA_CLIENT_ID"], 
            st.secrets["ASTRA_CLIENT_SECRET"]
        )
        
        # Connection au cluster via l'argument 'cloud='
        cluster = Cluster(
            cloud=cloud_config, 
            auth_provider=auth_provider
        )
        session = cluster.connect('notification_app')
        return session
    except Exception as e:
        st.error(f"Erreur lors de la connexion à Astra DB : {e}")
        return None

# Initialisation de la session
session = get_cassandra_session()

if session is None:
    st.warning("⚠️ Connexion impossible. Vérifiez secrets.toml et le nom du fichier .zip.")
    st.stop()

st.success("⚡ Connecté à Cassandra (Astra DB) avec succès !")
st.title("🔔 Système de Suivi de Notifications")

col_send, col_view = st.columns([1, 1])

# --- Formulaire d'envoi de notification ---
with col_send:
    st.header("Envoyer une Notification")
    with st.form("send_notif_form"):
        user_id = st.text_input("ID Utilisateur", "usr_101")
        title = st.text_input("Titre", "Alerte Sécurité")
        message = st.text_area("Message", "Nouvelle connexion détectée sur votre compte.")
        category = st.selectbox("Catégorie", ["INFO", "WARNING", "ALERT"])
        
        submitted = st.form_submit_button("Envoyer")
        
        if submitted:
            try:
                query = """
                INSERT INTO user_notifications (user_id, created_at, notification_id, title, message, category, is_read)
                VALUES (%s, %s, now(), %s, %s, %s, false)
                """
                session.execute(query, (user_id, datetime.now(), title, message, category))
                st.success(f"Notification envoyée à {user_id} !")
            except Exception as e:
                st.error(f"Erreur lors de l'envoi : {e}")

# --- Visualisation des notifications ---
with col_view:
    st.header("Fil de Notifications")
    selected_user = st.text_input("Consulter l'utilisateur :", "usr_101")
    
    if selected_user:
        try:
            query = """
            SELECT created_at, category, title, message, is_read 
            FROM user_notifications 
            WHERE user_id = %s
            """
            rows = session.execute(query, (selected_user,))
            
            data = []
            for row in rows:
                data.append({
                    "Date": row.created_at,
                    "Catégorie": row.category,
                    "Titre": row.title,
                    "Message": row.message,
                    "Lu": row.is_read
                })
            
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Aucune notification pour cet utilisateur.")
        except Exception as e:
            st.error(f"Erreur lors de la lecture : {e}")