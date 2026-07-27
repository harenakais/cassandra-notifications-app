import os
os.environ['CASSANDRA_DRIVER_NO_EXTENSIONS'] = '1'

import streamlit as st
from datetime import datetime
import pandas as pd

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

# --- Configuration de la page ---
st.set_page_config(
    page_title="Notifications Cassandra", 
    page_icon="🔔",
    layout="wide"
)

# --- Connexion à Astra DB ---
@st.cache_resource
def get_cassandra_session():
    try:
        # Résolution du chemin absolu du fichier .zip pour Streamlit Cloud
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        bundle_path = os.path.join(BASE_DIR, 'secure-connect-notification-db.zip')

        cloud_config = {
            'secure_connect_bundle': bundle_path
        }
        auth_provider = PlainTextAuthProvider(
            st.secrets["ASTRA_CLIENT_ID"], 
            st.secrets["ASTRA_CLIENT_SECRET"]
        )
        
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
    st.warning("⚠️ Connexion impossible. Vérifiez secrets.toml et le fichier .zip.")
    st.stop()

st.title("🔔 Système de Suivi de Notifications")

# Dictionnaire de style pour les catégories
CATEGORY_STYLES = {
    "INFO": "🔵 INFO",
    "WARNING": "🟠 WARNING",
    "ALERT": "🔴 ALERT"
}

col_send, col_view = st.columns([1, 1], gap="large")

# --- Formulaire d'envoi de notification ---
with col_send:
    st.subheader("📤 Envoyer une Notification")
    with st.form("send_notif_form", clear_on_submit=True):
        user_id = st.text_input("ID Utilisateur", "usr_101")
        title = st.text_input("Titre", "Alerte Sécurité")
        message = st.text_area("Message", "Nouvelle connexion détectée sur votre compte.")
        category = st.selectbox("Catégorie", ["INFO", "WARNING", "ALERT"])
        
        submitted = st.form_submit_button("Envoyer la notification", use_container_width=True)
        
        if submitted:
            if not user_id.strip() or not title.strip():
                st.warning("Veuillez remplir au moins l'ID utilisateur et le titre.")
            else:
                try:
                    query = """
                    INSERT INTO user_notifications (user_id, created_at, notification_id, title, message, category, is_read)
                    VALUES (%s, %s, now(), %s, %s, %s, false)
                    """
                    session.execute(query, (user_id.strip(), datetime.now(), title, message, category))
                    st.success(f"Notification envoyée à {user_id} !")
                except Exception as e:
                    st.error(f"Erreur lors de l'envoi : {e}")

# --- Visualisation des notifications ---
with col_view:
    st.subheader("📋 Fil de Notifications")
    
    col_input, col_refresh = st.columns([3, 1])
    with col_input:
        selected_user = st.text_input("Consulter l'utilisateur :", "usr_101")
    with col_refresh:
        st.write("") # Espace pour aligner le bouton avec le champ texte
        st.write("") 
        btn_refresh = st.button("🔄 Actualiser", use_container_width=True)

    if selected_user:
        try:
            query = """
            SELECT created_at, notification_id, category, title, message, is_read 
            FROM user_notifications 
            WHERE user_id = %s
            """
            rows = session.execute(query, (selected_user.strip(),))
            
            # Conversion des résultats
            notifications = list(rows)
            
            if notifications:
                # Tri des notifications (plus récente en premier)
                notifications.sort(key=lambda x: x.created_at, reverse=True)
                
                # Compteurs simples
                unread_count = sum(1 for n in notifications if not n.is_read)
                st.caption(f"Total : **{len(notifications)}** | Non lues : **{unread_count}**")
                
                # Affichage sous forme de cartes dynamiques
                for idx, notif in enumerate(notifications):
                    badge = CATEGORY_STYLES.get(notif.category, "⚪ INFO")
                    status_str = "✅ Lu" if notif.is_read else "🔴 Non lu"
                    
                    with st.container(border=True):
                        col_header, col_status = st.columns([3, 1])
                        with col_header:
                            st.markdown(f"**{badge}** — **{notif.title}**")
                        with col_status:
                            st.caption(status_str)
                            
                        st.write(notif.message)
                        st.caption(f"📅 {notif.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # Bouton pour marquer comme lu si non lu
                        if not notif.is_read:
                            if st.button("Marquer comme lu", key=f"read_{notif.notification_id}"):
                                try:
                                    update_query = """
                                    UPDATE user_notifications 
                                    SET is_read = true 
                                    WHERE user_id = %s AND created_at = %s AND notification_id = %s
                                    """
                                    session.execute(update_query, (selected_user.strip(), notif.created_at, notif.notification_id))
                                    st.toast("Notification marquée comme lue !")
                                    st.rerun()
                                except Exception as update_err:
                                    st.error(f"Impossible de mettre à jour : {update_err}")
            else:
                st.info("Aucune notification pour cet utilisateur.")
        except Exception as e:
            st.error(f"Erreur lors de la lecture : {e}")
