import psycopg2
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import re
import os

# Database connection
def connect_db():
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sportal_database_user:6h6G3tE82CnKPjF5fXbFY4tT6ffZD3Aa@dpg-crn2e6l6l47c73a8ll0g-a.singapore-postgres.render.com/sportal_database')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")

    conn = psycopg2.connect(DATABASE_URL)
    #Replace user and password with your Postgres username and password, host and #port with the values in your database URL, and database_name with the name of #your database.

    return conn

# Insert or update club data into the database
def insert_club_data(conn, email, club_data):
    print("INSERT DATA CHECK", email)
    cursor = conn.cursor()
    query = """
    INSERT INTO clubs_dirty (email, clubdata)
    VALUES (%s, %s)
    ON CONFLICT (email)
    DO UPDATE SET clubdata = EXCLUDED.clubdata
    """
    cursor.execute(query, (email, json.dumps(club_data)))
    conn.commit()
    cursor.close()


def get_players(isHome, link, driver):
    playerList = []

    pos = 1
    if isHome:
        pos = 0

    try:
        driver.get(f'https://www.playhq.com{link}')
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        teamsSets = soup.find_all('table', class_='sc-155yh5n-2 jFvwue')

        if len(teamsSets) == 2:
            print("I AM FINALLY GETTING")
            player_rows = teamsSets[pos].find_all('tr', attrs={'data-testid': lambda x: x and x.startswith('player-')})
            for row in player_rows:
                # Find the full name by looking inside <span> tags
                name_spans = row.find_all('span')
                name = name_spans[0].get_text()  # First <span> has the first name
                if 'Private' not in name:
                    print(name)
                    playerList.append(name)
        
    except Exception as e:
        print('Ran into error: ')
    
    return playerList

# Fetch and parse data
def get_fixtures(soup, team_name, driver):
    print("FIXTURE TEST 0")
    fixture_list = soup.find_all('div', class_='sc-fnpp5x-0 sc-fnpp5x-5 boRXYi iSdlQK')
    fixtures = []
    print("FIXTURE TEST 1", len(fixture_list))

    for fixture in fixture_list:
        # Initialize default values
        fixture_name = "Unknown Fixture"
        fixture_date = "Unknown Date"
        fixture_format = "Unknown Format"
        fixture_venue = "Unknown Venue"
        team_a = "Team A"
        team_a_logo = "https://pngfre.com/wp-content/uploads/Cricket-14-1.png"
        team_b = "Team B"
        team_b_logo = "https://pngfre.com/wp-content/uploads/Cricket-14-1.png"
        playerList = []

        try:
            # Attempt to extract fixture name and date
            arrowLink = fixture.find('a', class_='sc-10c3c88-6 gdEmqr')["href"]
            fixture_name_tag = fixture.find('h3', class_="sc-kpDqfm sc-10c3c88-1 bAhzTo fLyUTG")
            fixture_name = fixture_name_tag.get_text() if fixture_name_tag else fixture_name

            fixture_date_tag = fixture.find('span', class_="sc-gFqAkR jPxLpB")
            fixture_date = fixture_date_tag.get_text() if fixture_date_tag else fixture_date

            teams_div = fixture.find_all('div', class_="sc-12j2xsj-0 jXoewb")

            print("FIXTURE TEST 2", fixture_name, "-", fixture_date, "-", arrowLink)

            # Handle team A
            team_a_div = teams_div[0] if len(teams_div) > 0 else None
            print("FIXTURE TEST 3 ", team_a_div)
            if team_a_div:
                team_a_link = team_a_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 dHxVeH cdnZHA") or \
                              team_a_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 gDVNBY cdnZHA")
                team_a = team_a_link.get_text() if team_a_link else team_a
                if (team_a == team_name):
                    print("IS HOME TEAM")
                    playerList = get_players(True,arrowLink,driver)
                team_a_logo_tag = team_a_div.find('img')
                team_a_logo = team_a_logo_tag.get('src') if team_a_logo_tag else team_a_logo


            # Handle team B
            team_b_div = teams_div[1] if len(teams_div) > 1 else None
            if team_b_div:
                team_b_link = team_b_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 dHxVeH cdnZHA") or \
                              team_b_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 gDVNBY cdnZHA")
                team_b = team_b_link.get_text() if team_b_link else team_b
                if (team_b == team_name):
                    print("NOT HOME TEAM")
                    playerList = get_players(False,arrowLink, driver)
                team_b_logo_tag = team_b_div.find('img')
                team_b_logo = team_b_logo_tag.get('src') if team_b_logo_tag else team_b_logo

            fixture_card = fixture.find('div', class_="sc-10c3c88-11 GJoRe")

            fixture_venue_tag = fixture_card.find('a', class_="sc-kpDqfm sc-10c3c88-16 benLvT gIKUwU")
            fixture_venue = fixture_venue_tag.get_text() if fixture_venue_tag else fixture_venue

            fixture_format_tag = fixture_card.find('span', class_="sc-kpDqfm sc-10c3c88-12 htBoat ffHzsh")
            fixture_format = fixture_format_tag.get_text() if fixture_format_tag else fixture_format

        except Exception as e:
            print(f"Error parsing fixture: {e}")  # Log the error for debugging purposes, but continue

        # Append the fixture with whatever data was found or default values
        fixtures.append({
            "fixtureName": fixture_name,
            "fixtureDate": fixture_date,
            "fixtureFormat": fixture_format,
            "fixtureVenue": fixture_venue,
            "teamA": team_a,
            "teamALogo": team_a_logo,
            "teamB": team_b,
            "teamBLogo": team_b_logo,
            "playerList": playerList
        })

    return fixtures

def get_teams(soup, seasonName, driver):
    print("TEAMS CHECK", seasonName)
    teams = []
    team_list = soup.find('ul', class_=re.compile(r"emEiLO$")).find_all('li')[1:]
    print("TEAMS CHECK 1", len(team_list))
    for team in team_list:
        try:
            
            team_name = team.find('span', class_='sc-kpDqfm kvnOPN').get_text()
            team_link = f'https://www.playhq.com{team.find("a", class_="sc-1c9d0lx-6 eYEzkz")["href"]}'
            print("TEAMS CHECK 2", team_link)
            # Load fixtures for the team
            driver.get(team_link)
            team_soup = BeautifulSoup(driver.page_source, 'html.parser')
            fixtures = get_fixtures(team_soup, team_name, driver)
            
            teams.append({
                "teamName": team_name,
                "fixtures": fixtures
            })
        except AttributeError:
            continue
    print("TEAMS CHECK 3", teams)
    return teams

def get_club_info(conn, url, email, driver):
    try:
        print(f"Loading URL: {url}")
        driver.get(url)
        
        # Wait for the page to load completely
        wait = WebDriverWait(driver, 20)  # 20 seconds timeout
        print("Waiting for page to load...")
        
        # Wait for the club name element to be present
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "organisation-name")))
            time.sleep(2)  # Additional small delay to ensure dynamic content loads
        except TimeoutException:
            print("Timeout waiting for club name to load")
        
        print("Page loaded, parsing content...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Initialize the JSON structure for club data
        club_data = {
            "clubName": "",
            "clubLogo": "",
            "association": []
        }

        # Get club name and logo with better error handling
        try:
            print("Extracting club details...")
            club_name_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "organisation-name")))
            club_name = club_name_element.text
            
            logo_element = driver.find_element(By.CLASS_NAME, "guhTET")
            club_logo = logo_element.find_element(By.TAG_NAME, "img").get_attribute("src")
            
            club_data["clubName"] = club_name
            club_data["clubLogo"] = club_logo
            print(f"Found club: {club_name}")
        except Exception as e:
            print(f"Error getting club details: {str(e)}")
            club_data["clubName"] = "Unknown Club"
        
        print(club_data)

        # Get associations and their competitions with better waiting
        counter = 0
        associanLength = len(wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "csoyBY"))))
        while counter < associanLength:
            driver.get(url)
            associations = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "csoyBY")))
            try:
                print("Processing association...")
                association_html = associations[counter].get_attribute('outerHTML')
                association_soup = BeautifulSoup(association_html, 'html.parser')
                
                # Fetch association name and logo
                association_name = association_soup.find('span', class_=re.compile(r"organisation-name$")).get_text()
                association_logo = association_soup.find('div', class_="sc-e3sm8r-0 dQQPAx sc-3lpl8o-4 jkyKuu").find('img').get('src')
                print(f"Processing association: {association_name}")

                # Find all competitions
                competitions = association_soup.find_all('div', class_=False)
                association_competitions = []
                
                for competition in competitions:
                    try:
                        competition_name = competition.find('h2', class_='sc-kpDqfm sc-s41lvh-4 bAhzTo cZpNhh').get_text()
                        print(f"Processing competition: {competition_name}")
                        seasons = []
                        seasons_ul = competition.find_all('ul')

                        for season in seasons_ul:
                            for li in season.find_all('li'):
                                season_name = li.find('span', class_='sc-kpDqfm sc-s41lvh-5 kvnOPN lffCOc').get_text()
                                link = f'https://www.playhq.com{li.find("a", class_="sc-s41lvh-3 dImJDh")["href"]}'
                                print(f"Loading season: {season_name} at {link}")
                                
                                # Load teams for the season with proper waiting
                                driver.get(link)
                                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "emEiLO")))
                                time.sleep(2)  # Give time for dynamic content to load
                                
                                season_soup = BeautifulSoup(driver.page_source, 'html.parser')
                                teams = get_teams(season_soup, season_name, driver)
                                
                                seasons.append({
                                    "seasonName": season_name,
                                    "teams": teams
                                })
                        
                        association_competitions.append({
                            "competitionName": competition_name,
                            "seasons": seasons
                        })
                    except Exception as e:
                        print(f"Error processing competition: {str(e)}")
                        continue

                club_data["association"].append({
                    "associationName": association_name,
                    "associationLogo": association_logo,
                    "competitions": association_competitions
                })
            except Exception as e:
                print(f"Error processing association: {str(e)}")
                continue
            counter+=1

        print("Inserting data into database...")
        insert_club_data(conn, email, club_data)
        print("Data insertion complete")

    except Exception as e:
        print(f"Major error in get_club_info: {str(e)}")
    finally:
        driver.quit()


# Main
if __name__ == "__main__":
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--headless=new')  # Use the new headless mode
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--enable-javascript')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # Prevents detection as automated browser
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])  # Prevents detection as automated browser
    chrome_options.add_experimental_option('useAutomationExtension', False)  # Prevents detection as automated browser
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')  # Use a modern user agent
    
    # Define your email and URL pairs
    club_data = [
        ("timmurphy1181@gmail.com", "https://www.playhq.com/cricket-australia/org/ashburton-willows-cricket-club/55f5bdce"),
        ("test@ashburton.com", "https://www.playhq.com/cricket-australia/org/ashburton-willows-cricket-club/55f5bdce"),
        ("test@carnegie.com", "https://www.playhq.com/cricket-australia/org/carnegie-cricket-club/df628a00"),
        ("test@cucckings.com", "https://www.playhq.com/cricket-australia/org/cucc-kings/6e4ab302"),
        ("test@murrumbeena.com", "https://www.playhq.com/cricket-australia/org/murrumbeena-cricket-club/de3182fc"),
        ("test@monashcc.com", "https://www.playhq.com/cricket-australia/org/monash-cricket-club/2a74f308")
    ]

    # Loop through each set and call the method
    for email, url in club_data:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'})
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")  # Prevents detection as automated browser

        conn = connect_db()
        get_club_info(conn, url, email, driver)
        conn.close()
