import time
import datetime
import requests
import sys
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service # Important pour Linux
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

# --- CONFIGURATION UTILISATEUR ---
DISCORD_WEBHOOK = "VOTRE_WEB_HOOK_DISCORD" 
EMAIL_ECOLE = "VOTRE_EMAIL@edu.devinci.fr"
MOT_DE_PASSE = "VOTRE_MOT_DE_PASSE."

# --- CONFIG TECHNIQUE RASPBERRY PI ---
URL_DASHBOARD = "https://my.devinci.fr/student/presences/"
# On stocke le profil dans le dossier de l'utilisateur courant 
CHROME_PROFILE_PATH = os.path.join(os.getcwd(), "BotPresence_Profile")

def log(message):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

def envoyer_notif(message):
    log(f"🔔 {message}")
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except:
        pass

def connexion_ecole_custom(driver):
    log("🔐 Connexion au portail De Vinci...")
    wait = WebDriverWait(driver, 15)

    try:
        if "my.devinci.fr" in driver.current_url:
            log("Etape 1: Saisie de l'email...")
            email_field = wait.until(EC.visibility_of_element_located((By.ID, "login")))
            email_field.clear()
            email_field.send_keys(EMAIL_ECOLE)
            
            btn_next = driver.find_element(By.ID, "btn_next")
            btn_next.click()
        
        log("Attente de la redirection vers la page mot de passe...")
        wait.until(EC.visibility_of_element_located((By.ID, "passwordInput")))
        
        log("Etape 2: Saisie du mot de passe...")
        pwd_field = driver.find_element(By.ID, "passwordInput")
        pwd_field.clear()
        pwd_field.send_keys(MOT_DE_PASSE)
        
        log("Validation finale...")
        btn_submit = driver.find_element(By.ID, "submitButton")
        btn_submit.click()
        
        log("Attente du retour sur l'emploi du temps...")
        time.sleep(5)
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
        if "alert-success" in src and "Vous avez été noté présent" in src:
            return 2 
            
        boutons_potentiels = driver.find_elements(By.XPATH, "//span[contains(text(), 'Valider la présence')]")
        
        for btn in boutons_potentiels:
            try:
                if btn.is_displayed():
                    classes = btn.get_attribute("class")
                    if "btn-success" in classes:
                        return 1 
            except:
                continue
        return 0
    except Exception as e:
        return 0

def pause_intelligente(secondes, driver):
    for _ in range(int(secondes)):
        try:
            _ = driver.window_handles
            time.sleep(1)
        except WebDriverException:
            log("❌ Fenêtre fermée. Arrêt immédiat.")
            sys.exit()

def demarrer_bot():
    log("🚀 Démarrage Assistant Présence V4 (Mode Raspberry Pi)")
    
    # --- CONFIGURATION CHROME POUR RASPBERRY ---
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
    
    # INDISPENSABLE : Mode sans tête (pas d'écran)
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage") # Évite les crashs mémoire sur le Pi
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    
    # On pointe vers le driver installé via APT
    service = Service("/usr/bin/chromedriver")

    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        log(f"❌ Erreur critique au lancement de Chrome : {e}")
        log("Vérifiez que 'chromium-driver' est bien installé.")
        return

    try:
        driver.get(URL_DASHBOARD)
        pause_intelligente(3, driver)
        
        # --- BLOC CONNEXION ---
        url_actuelle = driver.current_url
        if "login" in driver.page_source or "adfs" in url_actuelle or "my.devinci.fr" == url_actuelle.strip('/'):
            if "student/presences" not in url_actuelle:
                reussite = connexion_ecole_custom(driver)
                if not reussite:
                    driver.quit()
                    return
                
                log("Redirection forcée vers le planning...")
                driver.get(URL_DASHBOARD)
                pause_intelligente(3, driver)
        else:
            log("Déjà connecté.")

        cours_en_cours_url = None
        
        while True:
            try:
                _ = driver.window_handles
            except WebDriverException:
                log("❌ Chrome crashé."); sys.exit()

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
                    driver.get(cours_en_cours_url)
                else:
                    log("💤 Aucun cours. Pause 5 min.")
                    # IMPORTANT : Sur un serveur, on évite les boucles infinies trop rapides
                    # time.sleep consomme moins de CPU que la boucle pause_intelligente
                    time.sleep(300) 
            
            else:
                try:
                    if cours_en_cours_url not in driver.current_url:
                        log("⚠️ Ejection détectée ! Retour forcé...")
                        driver.get(cours_en_cours_url)
                        pause_intelligente(5, driver)
                    else:
                        driver.refresh()
                        pause_intelligente(4, driver) 
                    
                    etat = verifier_bouton_visible(driver)
                    
                    if etat == 1:
                        envoyer_notif(f"🚨 PRÉSENCE OUVERTE !!! \n{cours_en_cours_url}")
                        log("ALERTE : PRÉSENCE OUVERTE !")
                        # print('\a') # Le bip sonore ne marchera pas sur le Pi, on l'enlève
                        log("Pause 15 min après détection...")
                        time.sleep(900)
                        cours_en_cours_url = None 

                    elif etat == 2:
                        log("✅ Validé. Retour menu.")
                        cours_en_cours_url = None
                        pause_intelligente(5, driver)
                    else:
                        log("👀 Bouton caché...")
                        time.sleep(30)
                        
                except Exception as e:
                    log(f"Erreur boucle : {e}")
                    time.sleep(10)

    except KeyboardInterrupt:
        log("Arrêt demandé.")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    demarrer_bot()