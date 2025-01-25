import json
import os

class Config:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.default_config = {
            "openai": {
                "api_key": "",
                "api_base": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "database": {
                "path": "novel_writer.db"
            },
            "generation": {
                "outline": {
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                "content": {
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            }
        }
        self.config = self.load_config()
        self.validate_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self.default_config

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_openai_config(self):
        return self.config.get("openai", {})

    def get_database_config(self):
        return self.config.get("database", {})

    def get_generation_config(self, type="content"):
        return self.config.get("generation", {}).get(type, {})

    def validate_config(self):
        """校验配置文件有效性"""
        if not 0 <= self.config['openai']['temperature'] <= 2:
            raise ValueError("Temperature 参数需在0-2之间")
        if self.config['openai']['api_key'] == "":
            raise ValueError("缺少OpenAI API密钥")

class ConfigManager:
    def __init__(self, config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def get_openai_config(self):
        return self.config.get('openai', {})
    
    def get_generation_config(self, config_type):
        return self.config.get('generation', {}).get(config_type, {}) 