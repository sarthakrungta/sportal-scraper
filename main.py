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
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)

# Database connection
def connect_db():
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sportal_database_user:6h6G3tE82CnKPjF5fXbFY4tT6ffZD3Aa@dpg-crn2e6l6l47c73a8ll0g-a.singapore-postgres.render.com/sportal_database')
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")

        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

# Insert or update club data into the database
def insert_club_data(conn, email, club_data):
    try:
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
        logger.info(f"Successfully inserted/updated club data for email: {email}")
    except Exception as e:
        logger.error(f"Failed to insert/update club data for email {email}: {str(e)}")
        raise

def get_scores(link, driver, teamSidePos):
    logger.info(f"Starting get_scores for link: {link}, teamSidePos: {teamSidePos}")
    
    finalScoresJson = {
        "teamA": {
            "finalScore": "",
            "finalBreakdown": "",
            "periodScores": []
        },
        "teamB": {
            "finalScore": "",
            "finalBreakdown": "",
            "periodScores": []
        },
        "bestPlayers": ""
    }

    teams = ["teamA", "teamB"]

    try:
        url = f'https://www.playhq.com{link}'
        logger.info(f"Navigating to scores URL: {url}")
        driver.get(url)

        WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="scores"]'))
)

        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Get best players
        try:
            bestPlayersDivs = soup.find_all('div', class_='sc-shiof1-0 idEwle')
            if bestPlayersDivs and len(bestPlayersDivs) > teamSidePos:
                finalScoresJson["bestPlayers"] = bestPlayersDivs[teamSidePos].get_text()
                logger.info("Successfully extracted best players")
            else:
                logger.warning("Best players div not found or insufficient elements")
        except Exception as e:
            logger.error(f"Error getting best players: {str(e)}")

        # Get scores and breakdown
        try:
            finalScoreSets = soup.find_all('span', class_=lambda x: x and any("sc-1swl5w-13" in cls for cls in x.split()))
            finalScoreAndBreakdownTeamA = soup.find('span', class_=lambda x: x and any("sc-1swl5w-14" in cls for cls in x.split()))
            finalScoreAndBreakdownTeamB = soup.find('span', class_=lambda x: x and any("sc-1swl5w-15" in cls for cls in x.split()))
            periodScoreSets = soup.find_all('tr', class_='sc-2xhb8k-12 bGvXXJ')

            if len(finalScoreSets) == 2 and len(periodScoreSets) == 2:
                for i in range(2):
                    finalScoreAndBreakdown = finalScoreAndBreakdownTeamA if i == 0 else finalScoreAndBreakdownTeamB
                    if finalScoreAndBreakdown:
                        finalScore = finalScoreAndBreakdown.find('span').text if finalScoreAndBreakdown.find('span') else ""
                        finalBreakdown = finalScoreAndBreakdown.find('div').text if finalScoreAndBreakdown.find('div') else ""
                        finalScoresJson[teams[i]]["finalScore"] = finalScore
                        finalScoresJson[teams[i]]["finalBreakdown"] = finalBreakdown

                        periodScoresSpans = periodScoreSets[i].find_all('span')
                        periodScores = [periodScoresSpan.get_text(strip=True) for periodScoresSpan in periodScoresSpans[1:]][::2]
                        finalScoresJson[teams[i]]["periodScores"] = periodScores
                        logger.info(f"Successfully extracted scores for {teams[i]}")
            else:
                logger.warning(f"Unexpected number of score elements found (finalScoreSets: {len(finalScoreSets)}, periodScoreSets: {len(periodScoreSets)})")
        except Exception as e:
            logger.error(f"Error getting scores: {str(e)}")

    except Exception as e:
        logger.error(f"General error in get_scores: {str(e)}")

    logger.info(f"Completed get_scores with result: {finalScoresJson}")
    return finalScoresJson

def get_players(isHome, link, driver):
    logger.info(f"Starting get_players for isHome: {isHome}, link: {link}")
    playerList = []
    pos = 1 if not isHome else 0

    try:
        url = f'https://www.playhq.com{link}'
        logger.info(f"Navigating to players URL: {url}")
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
                
        teamsSets = soup.find_all('table', class_=lambda x: x and any(cls.startswith('sc-155yh5n-2') for cls in x.split()))

        if len(teamsSets) == 2:
            logger.info("Found both team sets")
            player_rows = teamsSets[pos].find_all('tr', attrs={'data-testid': lambda x: x and x.startswith('player-')})
            
            for row in player_rows:
                try:
                    name_spans = row.find_all('span')
                    if name_spans:
                        name = name_spans[0].get_text()
                        if 'Private' not in name:
                            playerList.append(name)
                            logger.debug(f"Added player: {name}")
                except Exception as e:
                    logger.warning(f"Error processing player row: {str(e)}")
        else:
            logger.warning(f"Unexpected number of team sets found: {len(teamsSets)}")
        
    except Exception as e:
        logger.error(f"Error in get_players: {str(e)}")
    
    logger.info(f"Completed get_players with {len(playerList)} players")
    return playerList

def get_fixtures(soup, team_name, driver):
    logger.info(f"Starting get_fixtures for team: {team_name}")
    fixture_list = soup.find_all('div', class_='sc-fnpp5x-0 sc-fnpp5x-5 boRXYi iSdlQK')
    fixtures = []
    logger.info(f"Found {len(fixture_list)} fixtures to process")

    for fixture in fixture_list:
        fixture_data = {
            "fixtureName": "Unknown Fixture",
            "fixtureDate": "Unknown Date",
            "fixtureFormat": "Unknown Format",
            "fixtureVenue": "Unknown Venue",
            "teamA": "Team A",
            "teamALogo": "https://pngfre.com/wp-content/uploads/Cricket-14-1.png",
            "teamB": "Team B",
            "teamBLogo": "https://pngfre.com/wp-content/uploads/Cricket-14-1.png",
            "playerList": [],
            "finalScores": {}
        }

        try:
            arrowLink = fixture.find('a', class_='sc-10c3c88-6 gdEmqr')["href"]
            fixture_name_tag = fixture.find('h3', class_="sc-kpDqfm sc-10c3c88-1 bAhzTo fLyUTG")
            fixture_date_tag = fixture.find('span', class_="sc-gFqAkR jPxLpB")
            
            if fixture_name_tag:
                fixture_data["fixtureName"] = fixture_name_tag.get_text()
            if fixture_date_tag:
                fixture_data["fixtureDate"] = fixture_date_tag.get_text()

            logger.info(f"Processing fixture: {fixture_data['fixtureName']} on {fixture_data['fixtureDate']}")

            teams_div = fixture.find_all('div', class_="sc-12j2xsj-0 jXoewb")
            if len(teams_div) < 2:
                logger.warning(f"Unexpected number of teams divs found: {len(teams_div)}")
                continue

            # Process Team A
            team_a_div = teams_div[0]
            if team_a_div:
                try:
                    team_a_link = team_a_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 dHxVeH cdnZHA") or \
                                  team_a_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 gDVNBY cdnZHA")
                    if team_a_link:
                        fixture_data["teamA"] = team_a_link.get_text()
                        if fixture_data["teamA"] == team_name:
                            logger.info("Our team is Team A (left side)")
                            fixture_data["finalScores"] = get_scores(arrowLink, driver, 0)
                            fixture_data["playerList"] = get_players(True, arrowLink, driver)
                    
                    team_a_logo_tag = team_a_div.find('img')
                    if team_a_logo_tag:
                        fixture_data["teamALogo"] = team_a_logo_tag.get('src')
                except Exception as e:
                    logger.error(f"Error processing Team A: {str(e)}")

            # Process Team B
            team_b_div = teams_div[1]
            if team_b_div:
                try:
                    team_b_link = team_b_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 dHxVeH cdnZHA") or \
                                  team_b_div.find('a', class_="sc-kpDqfm sc-12j2xsj-3 gDVNBY cdnZHA")
                    if team_b_link:
                        fixture_data["teamB"] = team_b_link.get_text()
                        if fixture_data["teamB"] == team_name:
                            logger.info("Our team is Team B (right side)")
                            fixture_data["playerList"] = get_players(False, arrowLink, driver)
                            fixture_data["finalScores"] = get_scores(arrowLink, driver, 1)
                    
                    team_b_logo_tag = team_b_div.find('img')
                    if team_b_logo_tag:
                        fixture_data["teamBLogo"] = team_b_logo_tag.get('src')
                except Exception as e:
                    logger.error(f"Error processing Team B: {str(e)}")

            # Process venue and format
            fixture_card = fixture.find('div', class_="sc-10c3c88-11 GJoRe")
            if fixture_card:
                try:
                    fixture_venue_tag = fixture_card.find('a', class_="sc-kpDqfm sc-10c3c88-16 benLvT gIKUwU")
                    if fixture_venue_tag:
                        fixture_data["fixtureVenue"] = fixture_venue_tag.get_text()
                    
                    fixture_format_tag = fixture_card.find('span', class_="sc-kpDqfm sc-10c3c88-12 htBoat ffHzsh")
                    if fixture_format_tag:
                        fixture_data["fixtureFormat"] = fixture_format_tag.get_text()
                except Exception as e:
                    logger.error(f"Error processing fixture details: {str(e)}")

        except Exception as e:
            logger.error(f"Error parsing fixture: {str(e)}")

        fixtures.append(fixture_data)
        logger.info(f"Completed processing fixture: {fixture_data['fixtureName']}")

    logger.info(f"Completed get_fixtures with {len(fixtures)} fixtures")
    return fixtures

def get_teams(soup, seasonName, driver):
    logger.info(f"Starting get_teams for season: {seasonName}")
    teams = []
    
    try:
        team_list_ul = soup.find('ul', class_=re.compile(r"emEiLO$"))
        if not team_list_ul:
            logger.warning("No team list ul found")
            return teams
            
        team_list = team_list_ul.find_all('li')[1:]
        logger.info(f"Found {len(team_list)} teams to process")
        
        for team in team_list:
            try:
                team_name = team.find('span', class_='sc-kpDqfm kvnOPN')
                if not team_name:
                    logger.warning("Team name not found in team element")
                    continue
                    
                team_name = team_name.get_text()
                team_link_tag = team.find("a", class_="sc-1c9d0lx-6 eYEzkz")
                if not team_link_tag:
                    logger.warning(f"No team link found for team: {team_name}")
                    continue
                    
                team_link = f'https://www.playhq.com{team_link_tag["href"]}'
                logger.info(f"Processing team: {team_name} at {team_link}")
                
                driver.get(team_link)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "sc-fnpp5x-0"))
                )
                team_soup = BeautifulSoup(driver.page_source, 'html.parser')
                fixtures = get_fixtures(team_soup, team_name, driver)
                
                teams.append({
                    "teamName": team_name,
                    "fixtures": fixtures
                })
                logger.info(f"Successfully processed team: {team_name}")
                
            except Exception as e:
                logger.error(f"Error processing team: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in get_teams: {str(e)}")
    
    logger.info(f"Completed get_teams with {len(teams)} teams")
    return teams

def get_club_info(conn, url, email, driver):
    logger.info(f"Starting get_club_info for URL: {url}, email: {email}")
    
    try:
        logger.info(f"Loading club URL: {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 20)
        logger.info("Waiting for page to load...")
        
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "organisation-name")))
            time.sleep(2)
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.error("Timeout waiting for club name to load")
            return
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        club_data = {
            "clubName": "Unknown Club",
            "clubLogo": "",
            "association": []
        }

        # Get club name and logo
        try:
            club_name_element = driver.find_element(By.CLASS_NAME, "organisation-name")
            club_data["clubName"] = club_name_element.text
            
            logo_element = driver.find_element(By.CLASS_NAME, "guhTET")
            club_logo = logo_element.find_element(By.TAG_NAME, "img").get_attribute("src")
            club_data["clubLogo"] = club_logo
            logger.info(f"Found club: {club_data['clubName']}")
        except Exception as e:
            logger.error(f"Error getting club details: {str(e)}")

        # Process associations
        try:
            associations = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "csoyBY")))
            associanLength = len(associations)
            logger.info(f"Found {associanLength} associations to process")
            
            for counter in range(associanLength):
                try:
                    driver.get(url)
                    associations = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "csoyBY")))
                    association_html = associations[counter].get_attribute('outerHTML')
                    association_soup = BeautifulSoup(association_html, 'html.parser')
                    
                    # Get association details
                    association_name = association_soup.find('span', class_=re.compile(r"organisation-name$"))
                    if not association_name:
                        logger.warning(f"Skipping association at index {counter} - name not found")
                        continue
                        
                    association_name = association_name.get_text()
                    association_logo_tag = association_soup.find('div', class_="sc-e3sm8r-0 dQQPAx sc-3lpl8o-4 jkyKuu")
                    association_logo = association_logo_tag.find('img').get('src') if association_logo_tag else ""
                    
                    logger.info(f"Processing association: {association_name}")
                    
                    competitions = association_soup.find_all('div', class_=False)
                    association_competitions = []
                    
                    for competition in competitions:
                        try:
                            competition_name_tag = competition.find('h2', class_='sc-kpDqfm sc-s41lvh-4 bAhzTo cZpNhh')
                            if not competition_name_tag:
                                logger.warning("Skipping competition - name not found")
                                continue
                                
                            competition_name = competition_name_tag.get_text()
                            logger.info(f"Processing competition: {competition_name}")
                            
                            seasons = []
                            seasons_ul = competition.find_all('ul')
                            
                            for season in seasons_ul:
                                for li in season.find_all('li'):
                                    try:
                                        season_name_tag = li.find('span', class_='sc-kpDqfm sc-s41lvh-5 kvnOPN lffCOc')
                                        season_link_tag = li.find("a", class_="sc-s41lvh-3 dImJDh")
                                        
                                        if not season_name_tag or not season_link_tag:
                                            logger.warning("Skipping season - name or link not found")
                                            continue
                                            
                                        season_name = season_name_tag.get_text()
                                        link = f'https://www.playhq.com{season_link_tag["href"]}'
                                        logger.info(f"Loading season: {season_name} at {link}")
                                        
                                        driver.get(link)
                                        try:
                                            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "emEiLO")))
                                            time.sleep(2)
                                            
                                            season_soup = BeautifulSoup(driver.page_source, 'html.parser')
                                            teams = get_teams(season_soup, season_name, driver)
                                            
                                            seasons.append({
                                                "seasonName": season_name,
                                                "teams": teams
                                            })
                                        except TimeoutException:
                                            logger.error(f"Timeout loading season page: {season_name}")
                                            continue
                                            
                                    except Exception as e:
                                        logger.error(f"Error processing season: {str(e)}")
                                        continue
                            
                            association_competitions.append({
                                "competitionName": competition_name,
                                "seasons": seasons
                            })
                            
                        except Exception as e:
                            logger.error(f"Error processing competition: {str(e)}")
                            continue
                    
                    club_data["association"].append({
                        "associationName": association_name,
                        "associationLogo": association_logo,
                        "competitions": association_competitions
                    })
                    logger.info(f"Completed processing association: {association_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing association at index {counter}: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"Error finding associations: {str(e)}")

        logger.info("Inserting data into database...")
        logger.info(club_data)
        insert_club_data(conn, email, club_data)
        logger.info("Data insertion complete")

    except Exception as e:
        logger.error(f"Major error in get_club_info: {str(e)}")
    finally:
        driver.quit()
        logger.info("WebDriver quit successfully")

if __name__ == "__main__":
    logger.info("Starting main execution")
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--enable-javascript')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    club_data = [
        ("monash@fida.org.au", "https://www.playhq.com/afl/org/monash-demons/242489e2"),
        ("test@monashdemons.com", "https://www.playhq.com/afl/org/monash-demons/242489e2"),
        ("test@monashblues.com", "https://www.playhq.com/afl/org/monash-blues/f55b375c"),
        #("timmurphy1181@gmail.com", "https://www.playhq.com/cricket-australia/org/ashburton-willows-cricket-club/55f5bdce"),
        #("test@ashburton.com", "https://www.playhq.com/cricket-australia/org/ashburton-willows-cricket-club/55f5bdce"),
        #("test@carnegie.com", "https://www.playhq.com/cricket-australia/org/carnegie-cricket-club/df628a00"),
        #("test@cucckings.com", "https://www.playhq.com/cricket-australia/org/cucc-kings/6e4ab302"),
        #("test@murrumbeena.com", "https://www.playhq.com/cricket-australia/org/murrumbeena-cricket-club/de3182fc"),
        #("test@monashcc.com", "https://www.playhq.com/cricket-australia/org/monash-cricket-club/2a74f308")

    ]

    for email, url in club_data:
        try:
            logger.info(f"Processing club: {url} for email: {email}")
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'})
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            conn = connect_db()
            get_club_info(conn, url, email, driver)
            conn.close()
            logger.info(f"Successfully processed club: {url}")
        except Exception as e:
            logger.error(f"Error processing club {url}: {str(e)}")
    
    logger.info("Main execution completed")