import json
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union
import requests
from qwen_agent.tools.base import BaseTool, register_tool
from prompt import EXTRACTOR_PROMPT 
from openai import OpenAI
import random
from urllib.parse import urlparse, unquote
import time 
from transformers import AutoTokenizer
import tiktoken
import re
from bs4 import BeautifulSoup

VISIT_SERVER_TIMEOUT = int(os.getenv("VISIT_SERVER_TIMEOUT", 200))
WEBCONTENT_MAXLENGTH = int(os.getenv("WEBCONTENT_MAXLENGTH", 150000))

# MODIFIED: Local ReaderLM configuration instead of Jina API
READERLM_ENDPOINT = os.getenv("READERLM_ENDPOINT", "http://localhost:8081/v1")
READERLM_AVAILABLE = os.getenv("READERLM_AVAILABLE", "false").lower() == "true"

@staticmethod
def truncate_to_tokens(text: str, max_tokens: int = 95000) -> str:
    encoding = tiktoken.get_encoding("cl100k_base")
    
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    
    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)

OSS_JSON_FORMAT = """# Response Formats
## visit_content
{"properties":{"rational":{"type":"string","description":"Locate the **specific sections/data** directly related to the user's goal within the webpage content"},"evidence":{"type":"string","description":"Identify and extract the **most relevant information** from the content, never miss any important information, output the **full original context** of the content as far as possible, it can be more than three paragraphs.","summary":{"type":"string","description":"Organize into a concise paragraph with logical flow, prioritizing clarity and judge the contribution of the information to the goal."}}}}"""

@register_tool('visit', allow_overwrite=True)
class Visit(BaseTool):
    name = 'visit'
    description = 'Visit webpage(s) and return the summary of the content.'
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": ["string", "array"],
                "items": {
                    "type": "string"
                    },
                "minItems": 1,
                "description": "The URL(s) of the webpage(s) to visit. Can be a single URL or an array of URLs."
        },
        "goal": {
                "type": "string",
                "description": "The goal of the visit for webpage(s)."
        }
        },
        "required": ["url", "goal"]
    }

    def __init__(self):
        super().__init__()
        # MODIFIED: Initialize local ReaderLM client
        if READERLM_AVAILABLE:
            self.readerlm_client = OpenAI(
                base_url=READERLM_ENDPOINT,
                api_key="dummy-key"
            )
            self.readerlm_model = "readerlm"
            print(f"✓ ReaderLM initialized at {READERLM_ENDPOINT}")
        else:
            self.readerlm_client = None
            print("⚠ ReaderLM not available - using fallback extraction")

    def call(self, params: Union[str, dict], **kwargs) -> str:
        try:
            url = params["url"]
            goal = params["goal"]
        except:
            return "[Visit] Invalid request format: Input must be a JSON object containing 'url' and 'goal' fields"

        start_time = time.time()
        
        # Create log folder if it doesn't exist
        log_folder = "log"
        os.makedirs(log_folder, exist_ok=True)

        if isinstance(url, str):
            response = self.readpage_local(url, goal)
        else:
            response = []
            assert isinstance(url, List)
            start_time = time.time()
            for u in url: 
                if time.time() - start_time > 900:
                    cur_response = "The useful information in {url} for user goal {goal} as follows: \n\n".format(url=url, goal=goal)
                    cur_response += "Evidence in page: \n" + "The provided webpage content could not be accessed. Please check the URL or file format." + "\n\n"
                    cur_response += "Summary: \n" + "The webpage content could not be processed, and therefore, no information is available." + "\n\n"
                else:
                    try:
                        cur_response = self.readpage_local(u, goal)
                    except Exception as e:
                        cur_response = f"Error fetching {u}: {str(e)}"
                response.append(cur_response)
            response = "\n=======\n".join(response)
        
        print(f'Summary Length {len(response)}; Summary Content {response}')
        return response.strip()
        
    def call_server(self, msgs, max_retries=2):
        api_key = os.environ.get("API_KEY")
        url_llm = os.environ.get("API_BASE")
        model_name = os.environ.get("SUMMARY_MODEL_NAME", "")
        client = OpenAI(
            api_key=api_key,
            base_url=url_llm,
        )
        for attempt in range(max_retries):
            try:
                chat_response = client.chat.completions.create(
                    model=model_name,
                    messages=msgs,
                    temperature=0.7
                )
                content = chat_response.choices[0].message.content
                if content:
                    try:
                        json.loads(content)
                    except:
                        # extract json from string 
                        left = content.find('{')
                        right = content.rfind('}') 
                        if left != -1 and right != -1 and left <= right: 
                            content = content[left:right+1]
                    return content
            except Exception as e:
                # print(e)
                if attempt == (max_retries - 1):
                    return ""
                continue

    # MODIFIED: New methods for local web extraction
    def fetch_raw_html(self, url: str) -> str:
        """Fetch raw HTML from URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            raise Exception(f"Failed to fetch URL {url}: {str(e)}")

    def pre_clean_html(self, html_content: str) -> str:
        """Pre-clean HTML using ReaderLM patterns"""
        patterns = {
            'SCRIPT_PATTERN': r'<[ ]*script.*?\/[ ]*script[ ]*>',
            'STYLE_PATTERN': r'<[ ]*style.*?\/[ ]*style[ ]*>',
            'META_PATTERN': r'<[ ]*meta.*?>',
            'COMMENT_PATTERN': r'<[ ]*!--.*?--[ ]*>',
            'LINK_PATTERN': r'<[ ]*link.*?>',
            'BASE64_IMG_PATTERN': r'<img[^>]+src="data:image/[^;]+;base64,[^"]+"[^>]*>',
            'SVG_PATTERN': r'(<svg[^>]*>)(.*?)(<\/svg>)'
        }
        
        def replace_svg(html: str, new_content: str = "this is a placeholder") -> str:
            return re.sub(
                patterns['SVG_PATTERN'], 
                lambda match: f"{match.group(1)}{new_content}{match.group(3)}", 
                html, 
                flags=re.DOTALL
            )
        
        def replace_base64_images(html: str, new_image_src: str = "#") -> str:
            return re.sub(patterns['BASE64_IMG_PATTERN'], f'<img src="{new_image_src}">', html)
        
        # Apply cleaning patterns
        for pattern_name, pattern in patterns.items():
            if pattern_name not in ['BASE64_IMG_PATTERN', 'SVG_PATTERN']:
                html_content = re.sub(pattern, "", html_content, flags=re.DOTALL | re.IGNORECASE)
        
        html_content = replace_base64_images(html_content)
        html_content = replace_svg(html_content)
        
        return html_content

    def convert_with_readerlm(self, html_content: str) -> str:
        """Convert HTML to Markdown using local ReaderLM"""
        try:
            # Limit content for ReaderLM context
            max_chars = 15000
            if len(html_content) > max_chars:
                html_content = html_content[:max_chars] + "\n<!-- Content truncated -->"
            
            response = self.readerlm_client.chat.completions.create(
                model=self.readerlm_model,
                messages=[{"role": "user", "content": html_content}],
                temperature=0,
                max_tokens=4000,
                stop=None
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"ReaderLM conversion failed: {e}")
            raise Exception(f"ReaderLM processing failed: {str(e)}")

    def fallback_extraction(self, html_content: str) -> str:
        """Fallback extraction when ReaderLM is not available"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'ads', 'iframe']):
                element.decompose()
            
            # Try to find main content
            main_content = None
            for selector in ['main', 'article', '.content', '#content', '.main', '#main']:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.find('body') or soup
            
            # Extract text with basic formatting
            text_parts = []
            for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li']):
                text = element.get_text(strip=True)
                if text and len(text) > 20:
                    if element.name.startswith('h'):
                        level = int(element.name[1])
                        text_parts.append('#' * level + ' ' + text)
                    else:
                        text_parts.append(text)
            
            extracted_text = '\n\n'.join(text_parts)
            lines = extracted_text.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
            
            result = '\n\n'.join(cleaned_lines[:100])  # Limit paragraphs
            return result if result else "Could not extract meaningful content"
            
        except Exception as e:
            return f"Fallback extraction failed: {str(e)}"

    # MODIFIED: Replace jina_readpage with local extraction
    def local_readpage(self, url: str) -> str:
        """Extract webpage content using local ReaderLM or fallback"""
        try:
            print(f"Extracting content from: {url}")
            
            # Step 1: Fetch raw HTML
            raw_html = self.fetch_raw_html(url)
            
            # Step 2: Pre-clean HTML
            cleaned_html = self.pre_clean_html(raw_html)
            
            # Step 3: Convert with ReaderLM or use fallback
            if READERLM_AVAILABLE and self.readerlm_client:
                try:
                    content = self.convert_with_readerlm(cleaned_html)
                    print(f"✓ ReaderLM extraction successful for {url}")
                    return content
                except Exception as e:
                    print(f"ReaderLM failed for {url}, using fallback: {e}")
                    return self.fallback_extraction(cleaned_html)
            else:
                print(f"Using fallback extraction for {url}")
                return self.fallback_extraction(cleaned_html)
                
        except Exception as e:
            print(f"Local extraction failed for {url}: {e}")
            return "[visit] Failed to read page."

    def html_readpage_local(self, url: str) -> str:
        """Wrapper for local page reading with retries"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                content = self.local_readpage(url)
                if content and not content.startswith("[visit] Failed to read page.") and content != "[visit] Empty content.":
                    return content
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_attempts - 1:
                    return "[visit] Failed to read page."
                time.sleep(0.5)
        return "[visit] Failed to read page."

    # MODIFIED: Replace readpage_jina with readpage_local
    def readpage_local(self, url: str, goal: str) -> str:
        """Main function for local webpage reading and processing"""
        summary_page_func = self.call_server
        max_retries = int(os.getenv('VISIT_SERVER_MAX_RETRIES', 1))

        # Use local extraction instead of Jina API
        content = self.html_readpage_local(url)

        if content and not content.startswith("[visit] Failed to read page.") and content != "[visit] Empty content." and not content.startswith("[document_parser]"):
            content = truncate_to_tokens(content, max_tokens=95000)
            messages = [{"role":"user","content": EXTRACTOR_PROMPT.format(webpage_content=content, goal=goal)}]
            parse_retry_times = 0
            raw = summary_page_func(messages, max_retries=max_retries)
            summary_retries = 3
            
            while len(raw) < 10 and summary_retries >= 0:
                truncate_length = int(0.7 * len(content)) if summary_retries > 0 else 25000
                status_msg = (
                    f"[visit] Summary url[{url}] " 
                    f"attempt {3 - summary_retries + 1}/3, "
                    f"content length: {len(content)}, "
                    f"truncating to {truncate_length} chars"
                ) if summary_retries > 0 else (
                    f"[visit] Summary url[{url}] failed after 3 attempts, "
                    f"final truncation to 25000 chars"
                )
                print(status_msg)
                content = content[:truncate_length]
                extraction_prompt = EXTRACTOR_PROMPT.format(
                    webpage_content=content,
                    goal=goal
                )
                messages = [{"role": "user", "content": extraction_prompt}]
                raw = summary_page_func(messages, max_retries=max_retries)
                summary_retries -= 1

            parse_retry_times = 2
            if isinstance(raw, str):
                raw = raw.replace("```json", "").replace("```", "").strip()
            while parse_retry_times < 3:
                try:
                    raw = json.loads(raw)
                    break
                except:
                    raw = summary_page_func(messages, max_retries=max_retries)
                    parse_retry_times += 1
            
            if parse_retry_times >= 3:
                useful_information = "The useful information in {url} for user goal {goal} as follows: \n\n".format(url=url, goal=goal)
                useful_information += "Evidence in page: \n" + "The provided webpage content could not be accessed. Please check the URL or file format." + "\n\n"
                useful_information += "Summary: \n" + "The webpage content could not be processed, and therefore, no information is available." + "\n\n"
            else:
                useful_information = "The useful information in {url} for user goal {goal} as follows: \n\n".format(url=url, goal=goal)
                useful_information += "Evidence in page: \n" + str(raw["evidence"]) + "\n\n"
                useful_information += "Summary: \n" + str(raw["summary"]) + "\n\n"

            if len(useful_information) < 10 and summary_retries < 0:
                print("[visit] Could not generate valid summary after maximum retries")
                useful_information = "[visit] Failed to read page"
            
            return useful_information

        else:
            useful_information = "The useful information in {url} for user goal {goal} as follows: \n\n".format(url=url, goal=goal)
            useful_information += "Evidence in page: \n" + "The provided webpage content could not be accessed. Please check the URL or file format." + "\n\n"
            useful_information += "Summary: \n" + "The webpage content could not be processed, and therefore, no information is available." + "\n\n"
            return useful_information

    # REMOVED: All Jina API methods (jina_readpage, html_readpage_jina, etc.)
    # They are replaced by local methods above
