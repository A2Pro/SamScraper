from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from openai import OpenAI
import re
import os
import time
import base64
import glob
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

os.makedirs("screenshots", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    page.goto("https://www.google.com")
    page.goto("https://sam.gov/search/?page=1&pageSize=25&sort=-modifiedDate&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5Bstatus%5D%5Bis_active%5D=true&sfm%5BagencyPicker%5D%5B0%5D%5BorgKey%5D=100000000&sfm%5BagencyPicker%5D%5B0%5D%5BorgText%5D=097%20-%20DEPT%20OF%20DEFENSE&sfm%5BagencyPicker%5D%5B0%5D%5BlevelText%5D=Dept%20%2F%20Ind.%20Agency&sfm%5BagencyPicker%5D%5B0%5D%5Bhighlighted%5D=true")
    
    time.sleep(2)
    source = page.content()
    
    with open("source.txt", "w", errors="ignore") as f:
        f.write(source)
    
    browser.close()

with open("source.txt", "r", encoding="utf-8", errors="ignore") as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')
opp_links = soup.find_all('a', href=re.compile(r'^/opp/.+/view$'))
base_url = "https://sam.gov"
first_5_links = [base_url + link['href'] for link in opp_links[:5]]

codes = []
for link in opp_links[:5]:
    match = re.search(r'/opp/(.+)/view', link['href'])
    if match:
        codes.append(match.group(1)[:10])

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    for i, (url, code) in enumerate(zip(first_5_links, codes), 1):
        folder_name = f"screenshots/link_{i}_{code}"
        os.makedirs(folder_name, exist_ok=True)
        
        try:
            page.goto(url, wait_until="networkidle")
            time.sleep(2)
            
            for screenshot_num in range(1, 6):
                screenshot_name = f"{folder_name}/screenshot_{screenshot_num}.png"
                page.screenshot(path=screenshot_name, full_page=False)
                if screenshot_num < 5:
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
            
        except Exception as e:
            print(e)
            continue
    
    browser.close()

screenshots_dir = "screenshots"
link_folders = []
for item in os.listdir(screenshots_dir):
    item_path = os.path.join(screenshots_dir, item)
    if os.path.isdir(item_path) and item.startswith("link_"):
        link_folders.append(item_path)

link_folders.sort()
for i, folder in enumerate(link_folders, 1):
    
    screenshot_files = sorted(glob.glob(f"{folder}/*.png"))
    
    if not screenshot_files:
        print(f"No screenshots found in {folder}")
        continue
    
    print(f"Analyzing {len(screenshot_files)} screenshots from {folder}")
    
    image_contents = []
    for img_path in screenshot_files:
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        image_contents.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}",
                "detail": "high"
            }
        })
    
    content = [
        {
            "type": "text", 
            "text": """Analyze these screenshots from a government procurement opportunity page. Please:

1. Summarize the key points - What is this opportunity about? Key requirements, deadlines, scope, etc.

2. Generate a fake bid/proposal outline - Create a realistic proposal structure that would respond to this opportunity, including:
   - Executive summary points
   - Technical approach sections
   - Key deliverables
   - Rough timeline
   - Any compliance requirements mentioned

3. Next step recommendations - What additional information or screenshots might be needed to fully understand this opportunity?

Please be thorough and specific based on what you can see in these screenshots."""
        }
    ] + image_contents
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=2000 #Not that rich!
        )
        
        analysis = response.choices[0].message.content
        
        output_file = f"{folder}/analysis.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Analysis for Link {i}\n")
            f.write("=" * 50 + "\n\n")
            f.write(analysis)
        
        print(f"Analysis saved to {output_file}")
        print("-" * 50)
        print(analysis)
        print("-" * 50)
        print(f"Successfully analyzed link {i}")
        
    except Exception as e:
        print(e)

print("Check the folder for results")