import time
import datetime
import requests
import sys
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException,WebDriverException

DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1458088781386092636/jH4y-IyP2R4ziCyAeoc4JKJHtpEGmIgUZtckHbDhRtwk8NjeA_nmjCS-wNJ22lZa02Yv" 

EMAIL_ECOLE = "come.ribault@edu.devinci.fr"
# Collez votre mot de passe entre les guillemets ci-dessous
MOT_DE_PASSE = "Amandine0402!!!."

# --- CONFIG TECHNIQUE ---
# J'ai retiré l'accent de "Présence" pour éviter les bugs Windows, ça créera un dossier BotPresence
CHROME_PROFILE_PATH = r"C:\BotPresence"
URL_DASHBOARD = "https://my.devinci.fr/student/presences/"

def log(message):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

def envoyer_notif(message):
    log(f"🔔 {message}")
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except:
        pass

def connexion_ecole_custom(driver):
    """Gère la connexion spécifique De Vinci (Page 1 -> ADFS Page 2)"""
    log("🔐 Connexion au portail De Vinci...")
    wait = WebDriverWait(driver, 15)

    try:
        # --- ETAPE 1 : Page my.devinci.fr (Juste l'email) ---
        if "my.devinci.fr" in driver.current_url:
            log("Etape 1: Saisie de l'email...")
            # Champ ID = login
            email_field = wait.until(EC.visibility_of_element_located((By.ID, "login")))
            email_field.clear()
            email_field.send_keys(EMAIL_ECOLE)
            
            # Bouton ID = btn_next
            log("Clic sur Suivant...")
            btn_next = driver.find_element(By.ID, "btn_next")
            btn_next.click()
        
        # --- ETAPE 2 : Transition vers ADFS ---
        log("Attente de la redirection vers la page mot de passe...")
        # On attend que le champ mot de passe (ID unique sur la page 2) apparaisse
        wait.until(EC.visibility_of_element_located((By.ID, "passwordInput")))
        
        # --- ETAPE 3 : Page ADFS (Mot de passe) ---
        log("Etape 2: Saisie du mot de passe...")
        pwd_field = driver.find_element(By.ID, "passwordInput")
        pwd_field.clear()
        pwd_field.send_keys(MOT_DE_PASSE)
        
        log("Validation finale...")
        btn_submit = driver.find_element(By.ID, "submitButton")
        btn_submit.click()
        
        # --- ETAPE 4 : Retour au dashboard ---
        log("Attente du retour sur l'emploi du temps...")
        time.sleep(5) # On attend juste que la redirection ADFS se fasse
        # On attend de voir le mot "presences" dans l'URL ou un élément du dashboard
        log("✅ Connexion réussie !")
        return True

    except Exception as e:
        log(f"❌ Erreur de connexion : {e}")
        return False

def nettoyer_heure(texte_heure):
    try:
        clean = texte_heure.replace('\n', '').replace(' ', '')
        debut_str, fin_str = clean.split('-')
        now = datetime.datetime.now()
        debut = now.replace(hour=int(debut_str.split(':')[0]), minute=int(debut_str.split(':')[1]), second=0)
        fin = now.replace(hour=int(fin_str.split(':')[0]), minute=int(fin_str.split(':')[1]), second=0)
        return debut, fin
    except:
        return None, None

def trouver_cours_actuel(html_source):
    soup = BeautifulSoup(html_source, 'html.parser')
    rows = soup.select("#body_presences tr")
    maintenant = datetime.datetime.now()
    marge = datetime.timedelta(minutes=20) 

    for row in rows:
        cols = row.find_all('td')
        if not cols: continue 
        debut, fin = nettoyer_heure(cols[0].text)
        if not debut: continue

        if (debut - marge) <= maintenant <= fin:
            lien_tag = cols[3].find('a')
            if lien_tag and 'href' in lien_tag.attrs:
                url = lien_tag['href']
                if url.startswith('/'):
                    return "https://my.devinci.fr" + url
                return url
    return None

def verifier_bouton_visible(driver):
    try:
        src = driver.page_source
        
        # 1. Est-ce qu'on a déjà validé ?
        # On regarde si l'alerte verte de succès est là
        if "alert-success" in src and "Vous avez été noté présent" in src:
            return 2 # Déjà fait
            
        # 2. Chercher TOUS les éléments qui contiennent le texte "Valider la présence"
        # Car l'ID du vrai bouton est aléatoire (ex: id="2d5X7MqmxH")
        boutons_potentiels = driver.find_elements(By.XPATH, "//span[contains(text(), 'Valider la présence')]")
        
        for btn in boutons_potentiels:
            try:
                # On vérifie s'il est affiché à l'écran (taille > 0 et pas hidden)
                if btn.is_displayed():
                    # Petite vérif supplémentaire : est-ce que c'est bien le bouton vert ?
                    classes = btn.get_attribute("class")
                    if "btn-success" in classes:
                        return 1 # BINGO ! On a trouvé un bouton visible et vert
            except:
                continue # Si erreur sur un bouton, on teste le suivant
        
        return 0 # Aucun bouton visible trouvé
            
    except Exception as e:
        # En cas de gros bug, on considère que c'est pas ouvert
        return 0

# --- MAIN ---

def pause_intelligente(secondes, driver):
    """
    Fait une pause (ex: 300 secondes) mais vérifie chaque seconde 
    si la fenêtre est toujours ouverte.
    """
    for _ in range(int(secondes)):
        try:
            # On demande à Chrome : "Tu es toujours là ?"
            # Si la fenêtre est fermée, cette ligne plante et va dans 'except'
            _ = driver.window_handles
            
            # Si tout va bien, on dort 1 seconde
            time.sleep(1)
            
        except WebDriverException:
            # Si la fenêtre n'existe plus
            log("❌ Fenêtre fermée par l'utilisateur. Arrêt immédiat.")
            sys.exit() # On tue le script Python proprement

def demarrer_bot():
    log("🚀 Démarrage Assistant Présence V4 (Anti-Redirect)")
    
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
    
    # --- OPTIONS RASPBERRY LITE (Si besoin) ---
    # options.add_argument("--headless=new") 
    # options.add_argument("--no-sandbox") 
    # options.add_argument("--window-size=1920,1080")
    # ------------------------------------------
    
    # Initialisation du driver (Adapter 'service=' si sur Raspberry)
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(URL_DASHBOARD)
        pause_intelligente(3, driver)
        
        # --- BLOC CONNEXION ---
        url_actuelle = driver.current_url
        if "login" in driver.page_source or "adfs" in url_actuelle or "my.devinci.fr" == url_actuelle.strip('/'):
            if "student/presences" not in url_actuelle:
                reussite = connexion_ecole_custom(driver)
                if not reussite:
                    return
                
                log("Redirection forcée vers le planning...")
                driver.get(URL_DASHBOARD)
                pause_intelligente(3, driver)
        else:
            log("Déjà connecté.")

        cours_en_cours_url = None
        
        while True:
            # Sécurité : Vérifier si la fenêtre est ouverte
            try:
                _ = driver.window_handles
            except WebDriverException:
                log("❌ Fenêtre fermée. Bye !"); sys.exit()

            # MODE 1 : RECHERCHE DE COURS
            if not cours_en_cours_url:
                log("Scan planning...")
                
                if "presences" not in driver.current_url:
                    driver.get(URL_DASHBOARD)
                    pause_intelligente(3, driver)
                else:
                    driver.refresh()
                    pause_intelligente(3, driver)
                
                cours_en_cours_url = trouver_cours_actuel(driver.page_source)
                
                if cours_en_cours_url:
                    log(f"🎯 Cours trouvé : {cours_en_cours_url}")
                    envoyer_notif(f"Je surveille le cours : {cours_en_cours_url}")
                    driver.get(cours_en_cours_url)
                else:
                    log("💤 Aucun cours. Pause 5 min.")
                    pause_intelligente(300, driver) 
            
            # MODE 2 : SURVEILLANCE DU BOUTON
            else:
                try:
                    # --- FIX : LAISSE DE SECURITE ---
                    # Si le site nous a éjecté vers le menu principal, on force le retour
                    if cours_en_cours_url not in driver.current_url:
                        log("⚠️ Ejection détectée ! Retour forcé vers la salle de cours...")
                        driver.get(cours_en_cours_url)
                        pause_intelligente(5, driver) # On laisse charger
                    else:
                        # Si on est au bon endroit, on rafraichit simplement
                        driver.refresh()
                        pause_intelligente(4, driver) 
                    # -------------------------------
                    
                    etat = verifier_bouton_visible(driver)
                    
                    if etat == 1:
                        envoyer_notif(f"🚨 PRÉSENCE OUVERTE !!! \n{cours_en_cours_url}")
                        log("ALERTE : PRÉSENCE OUVERTE !")
                        print('\a') 
                        log("Pause 15 min...")
                        pause_intelligente(900, driver)
                        cours_en_cours_url = None 

                    elif etat == 2:
                        log("✅ Validé. Retour menu.")
                        cours_en_cours_url = None
                        pause_intelligente(5, driver)
                    else:
                        log("👀 Bouton caché...")
                        pause_intelligente(30, driver) 
                        
                except WebDriverException:
                    log("❌ Fenêtre fermée."); sys.exit()
                except Exception as e:
                    log(f"Erreur : {e}")
                    pause_intelligente(10, driver)

    except KeyboardInterrupt:
        log("Arrêt demandé.")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    demarrer_bot()