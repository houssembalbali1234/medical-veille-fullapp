import os
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger("medical_veille.email")

# ============================================================
# ⚙️ CONFIGURATION SMTP
# ============================================================

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Medical Veille <no-reply@medveille.com>")
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() == "true"
APP_URL = os.getenv("APP_URL", "http://localhost:3000")  # ✅ plus de hardcode


# ============================================================
# 📤 ENVOI D'EMAIL (vraiment async via aiosmtplib)
# ============================================================

async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None
) -> bool:
    """
    Envoie un email via SMTP asynchrone (aiosmtplib).
    Contrairement à smtplib, aiosmtplib ne bloque pas l'event loop —
    pas besoin de run_in_executor().

    text_body = version texte brut (fallback pour clients sans HTML)
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP non configuré — email non envoyé (SMTP_USER ou SMTP_PASSWORD manquant)")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=SMTP_TLS,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
        )

        logger.info(f"Email envoyé → {to} | sujet: {subject}")
        return True

    except aiosmtplib.SMTPAuthenticationError:
        logger.error("SMTP Auth failed — vérifiez SMTP_USER et SMTP_PASSWORD")
        return False
    except aiosmtplib.SMTPException as e:
        logger.error(f"Erreur SMTP → {to} : {e}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue envoi email → {to} : {e}")
        return False


# ============================================================
# 📧 DIGEST HEBDOMADAIRE — HTML
# ============================================================

def _build_digest_html(
    username: str,
    specialites: list[str],
    articles: list[dict],
    nb_notifications: int,
    periode: str
) -> str:
    """Construit le HTML responsive du digest hebdomadaire."""

    spec_badges = "".join([
        f'<span style="background:#e8f4fd;color:#2563eb;padding:4px 12px;'
        f'border-radius:20px;font-size:13px;margin:2px;display:inline-block;">'
        f'{s}</span>'
        for s in specialites
    ])

    articles_html = ""
    for i, article in enumerate(articles[:10], 1):
        titre     = article.get("titre",     "Sans titre")
        journal   = article.get("journal",   "")
        annee     = article.get("annee",     "")
        specialite = article.get("specialite", "")
        resume_ia = article.get("resume_ia", "")
        pubmed_id = article.get("pubmed_id", "")
        url       = article.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/")

        resume_section = ""
        if resume_ia:
            extrait = resume_ia[:300] + ("..." if len(resume_ia) > 300 else "")
            resume_section = f"""
            <p style="margin:8px 0 0;color:#4b5563;font-size:14px;
                      line-height:1.6;font-style:italic;">{extrait}</p>"""

        spec_badge = (
            f'<span style="background:#f0fdf4;color:#16a34a;padding:2px 8px;'
            f'border-radius:12px;font-size:12px;">{specialite}</span>'
            if specialite else ""
        )

        articles_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:10px;padding:16px;
                    margin-bottom:16px;background:#fff;">
          <div style="display:flex;justify-content:space-between;
                      align-items:flex-start;margin-bottom:8px;">
            <span style="font-size:12px;color:#6b7280;">#{i}</span>
            {spec_badge}
          </div>
          <h3 style="margin:0 0 6px;font-size:15px;color:#111827;
                     font-weight:600;line-height:1.4;">
            <a href="{url}" style="color:#2563eb;text-decoration:none;"
               target="_blank">{titre}</a>
          </h3>
          <p style="margin:0;font-size:13px;color:#9ca3af;">
            {journal}{f" · {annee}" if annee else ""}
          </p>
          {resume_section}
        </div>"""

    if not articles:
        articles_html = """
        <div style="text-align:center;padding:32px;color:#6b7280;">
          <p>Aucun nouvel article cette semaine dans vos spécialités.</p>
          <p style="font-size:14px;">Essayez d'ajouter de nouveaux mots-clés.</p>
        </div>"""

    notif_line = (
        f' Vous avez également <strong>{nb_notifications} notification(s)</strong> non lue(s).'
        if nb_notifications > 0 else ""
    )

    spec_section = f"""
    <div style="background:#fff;border-radius:12px;padding:20px;
                margin-bottom:20px;border:1px solid #e5e7eb;">
      <h3 style="margin:0 0 12px;font-size:15px;color:#374151;font-weight:600;">
        Vos spécialités
      </h3>
      <div>{spec_badges}</div>
    </div>""" if specialites else ""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Votre Digest Médical Hebdomadaire</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             background:#f9fafb;margin:0;padding:0;">
  <div style="max-width:640px;margin:0 auto;padding:24px 16px;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);
                border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
      <h1 style="color:#fff;margin:0 0 8px;font-size:24px;font-weight:700;">
        Medical Veille
      </h1>
      <p style="color:#bfdbfe;margin:0;font-size:15px;">
        Votre digest scientifique hebdomadaire
      </p>
      <p style="color:#93c5fd;margin:8px 0 0;font-size:13px;">
        Semaine du {periode}
      </p>
    </div>

    <!-- Intro -->
    <div style="background:#fff;border-radius:12px;padding:24px;
                margin-bottom:20px;border:1px solid #e5e7eb;">
      <h2 style="margin:0 0 12px;font-size:18px;color:#111827;">
        Bonjour {username}
      </h2>
      <p style="margin:0;color:#4b5563;font-size:15px;line-height:1.6;">
        Voici votre sélection personnalisée —
        <strong>{len(articles)} nouveaux articles</strong> dans vos spécialités.{notif_line}
      </p>
    </div>

    {spec_section}

    <!-- Articles -->
    <div style="background:#f8fafc;border-radius:12px;padding:20px;
                margin-bottom:20px;border:1px solid #e5e7eb;">
      <h3 style="margin:0 0 16px;font-size:16px;color:#111827;font-weight:600;">
        Nouveaux articles ({len(articles)})
      </h3>
      {articles_html}
    </div>

    <!-- CTA -->
    <div style="text-align:center;margin-bottom:24px;">
      <a href="{APP_URL}/dashboard/feed"
         style="background:#2563eb;color:#fff;padding:14px 32px;
                border-radius:8px;text-decoration:none;font-weight:600;
                font-size:15px;display:inline-block;">
        Voir mon feed complet →
      </a>
    </div>

    <!-- Footer -->
    <div style="text-align:center;color:#9ca3af;font-size:13px;
                padding-top:20px;border-top:1px solid #e5e7eb;">
      <p style="margin:0 0 8px;">
        Medical Veille · Plateforme de veille scientifique médicale
      </p>
      <p style="margin:0;">
        <a href="{APP_URL}/dashboard/alerts" style="color:#6b7280;">Gérer mes alertes</a>
        &nbsp;·&nbsp;
        <a href="{APP_URL}/dashboard/alerts" style="color:#6b7280;">Se désabonner</a>
      </p>
    </div>

  </div>
</body>
</html>"""


# ============================================================
# 📧 DIGEST HEBDOMADAIRE — TEXTE BRUT (fallback)
# ============================================================

def _build_digest_text(
    username: str,
    specialites: list[str],
    articles: list[dict],
    periode: str
) -> str:
    """Version texte brut du digest (fallback pour clients sans HTML)."""
    lines = [
        "Medical Veille — Digest hebdomadaire",
        f"Semaine du {periode}",
        "",
        f"Bonjour {username},",
        "",
        f"Voici votre sélection : {len(articles)} nouveaux articles.",
        "",
    ]

    if specialites:
        lines.append(f"Spécialités : {', '.join(specialites)}")
        lines.append("")

    lines.append("NOUVEAUX ARTICLES")
    lines.append("=" * 40)

    for i, article in enumerate(articles[:10], 1):
        titre     = article.get("titre",   "Sans titre")
        journal   = article.get("journal", "")
        annee     = article.get("annee",   "")
        pubmed_id = article.get("pubmed_id", "")
        url       = article.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/")

        lines.append(f"\n{i}. {titre}")
        if journal:
            lines.append(f"   {journal}{f' ({annee})' if annee else ''}")
        lines.append(f"   {url}")

    lines.extend([
        "",
        "---",
        f"Medical Veille | {APP_URL}",
        f"Gérer vos alertes : {APP_URL}/settings/alerts",
    ])

    return "\n".join(lines)


# ============================================================
# 📬 ENVOI DIGEST HEBDOMADAIRE
# ============================================================

async def send_weekly_digest(
    to_email: str,
    username: str,
    specialites: list[str],
    articles: list[dict],
    nb_notifications: int = 0
) -> bool:
    """
    Envoie le digest hebdomadaire personnalisé à un utilisateur.
    Appelé par Celery Beat chaque lundi à 8h.
    """
    now           = datetime.utcnow()
    semaine_debut = now - timedelta(days=7)
    mois_fr = {
        1: "janvier",  2: "février",  3: "mars",
        4: "avril",    5: "mai",      6: "juin",
        7: "juillet",  8: "août",     9: "septembre",
        10: "octobre", 11: "novembre", 12: "décembre"
    }
    periode = f"{semaine_debut.day}-{now.day} {mois_fr[now.month]} {now.year}"
    subject = f"Votre digest médical — {len(articles)} nouveaux articles ({periode})"

    return await send_email(
        to=to_email,
        subject=subject,
        html_body=_build_digest_html(username, specialites, articles, nb_notifications, periode),
        text_body=_build_digest_text(username, specialites, articles, periode),
    )


# ============================================================
# 🔔 EMAIL ALERTE IMMÉDIATE
# ============================================================

async def send_alert_notification(
    to_email: str,
    username: str,
    notification_type: str,   # "keyword" | "author"
    titre_notification: str,
    article_titre: str,
    pubmed_id: str,
    trigger_name: str
) -> bool:
    """
    Envoie un email immédiat quand une alerte est déclenchée.
    Complémentaire au push WebSocket — utile si l'utilisateur est hors ligne.

    trigger_name = le mot-clé ou le nom de l'auteur qui a déclenché l'alerte.
    """
    url        = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
    icon       = "🔑" if notification_type == "keyword" else "👤"
    type_label = "mot-clé" if notification_type == "keyword" else "auteur"

    html_body = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             background:#f9fafb;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;">

    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);
                border-radius:12px;padding:24px;margin-bottom:16px;text-align:center;">
      <h1 style="color:#fff;margin:0;font-size:20px;">Medical Veille</h1>
      <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Alerte de veille</p>
    </div>

    <div style="background:#fff;border-radius:12px;padding:24px;border:1px solid #e5e7eb;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#111827;">
        {icon} Nouvelle alerte {type_label}
      </h2>
      <p style="color:#4b5563;margin:0 0 12px;">Bonjour <strong>{username}</strong>,</p>
      <p style="color:#4b5563;margin:0 0 16px;">
        Un nouvel article correspond à votre suivi du {type_label}
        <strong>"{trigger_name}"</strong> :
      </p>
      <div style="background:#f0f9ff;border-left:4px solid #3b82f6;
                  padding:16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
        <p style="margin:0;font-weight:600;color:#1e40af;font-size:15px;">
          {article_titre}
        </p>
      </div>
      <a href="{url}"
         style="background:#2563eb;color:#fff;padding:12px 24px;
                border-radius:8px;text-decoration:none;font-weight:600;
                font-size:14px;display:inline-block;">
        Lire l'article →
      </a>
    </div>

    <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:16px;">
      <a href="{APP_URL}/settings/alerts" style="color:#9ca3af;">Gérer mes alertes</a>
    </p>
  </div>
</body>
</html>"""

    text_body = (
        f"Medical Veille — Alerte {type_label}\n\n"
        f"Bonjour {username},\n\n"
        f"Un nouvel article correspond à votre suivi '{trigger_name}' :\n"
        f"{article_titre}\n"
        f"{url}\n\n"
        f"Gérer vos alertes : {APP_URL}/settings/alerts"
    )

    return await send_email(
        to=to_email,
        subject=f"{icon} {titre_notification}",
        html_body=html_body,
        text_body=text_body,
    )