import openai
import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QMessageBox, QLineEdit, QLabel
from client.database import DatabaseManager
import sqlite3
import os

class Config:
    def __init__(self):
        self.config_path = "config.json"
        self.default_config = {
            "api_key": "",
            "model": "gpt-3.5-turbo",
            "max_tokens": 2000,
            "temperature": 0.7
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self.default_config

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

class ContentGenerator:
    def __init__(self, db_conn, api_key):
        self.db = db_conn
        openai.api_key = api_key
        openai.api_base = "https://api.openai.com/v1"  # 或者使用兼容API的地址
        
    def generate_chapter(self, project_id, chapter_index, style_params):
        """生成章节内容"""
        # 参数验证
        if not project_id or not chapter_index:
            raise ValueError("缺少必要的参数")
        
        try:
            # 获取大纲信息
            outline = self._get_outline(project_id)
            if not outline:
                raise ValueError("未找到项目大纲")
            
            # 构造提示词
            prompt = f"根据以下大纲生成第{chapter_index}章内容：\n"
            prompt += f"故事主线：{outline['main_storyline']}\n"
            prompt += f"本章标题：{outline['chapters'][chapter_index-1]}\n"
            prompt += f"写作风格：{style_params.get('style', '默认')}\n"
            prompt += f"字数要求：{style_params.get('length', 2000)}字\n"
            prompt += "请生成详细的章节内容，注意保持情节连贯性和人物性格一致性。"
            
            # 调用OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个专业的小说创作助手"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response['choices'][0]['message']['content']
            
            # 保存生成内容
            self._save_content(project_id, chapter_index, content)
            return content
        
        except openai.error.APIError as e:
            QMessageBox.critical(None, "API错误", f"OpenAI API调用失败: {str(e)}")
        except sqlite3.Error as e:
            QMessageBox.critical(None, "数据库错误", f"数据库操作失败: {str(e)}")
        except Exception as e:
            QMessageBox.critical(None, "未知错误", f"发生未知错误: {str(e)}")
        
    def _get_outline(self, project_id):
        """
        从数据库获取大纲
        :param project_id: 项目ID
        :return: 大纲内容
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT content FROM outlines WHERE project_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (project_id,))
        result = cursor.fetchone()
        return json.loads(result[0]) if result else {}
        
    def _save_content(self, project_id, chapter_index, content):
        """
        保存生成的章节内容
        :param project_id: 项目ID
        :param chapter_index: 章节序号
        :param content: 章节内容
        """
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO chapters (project_id, chapter_index, content)
            VALUES (?, ?, ?)
        """, (project_id, chapter_index, content))
        self.db.commit()

class ContentEditor(QWidget):
    def __init__(self, project_id, chapter_index, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.chapter_index = chapter_index
        self.init_ui()
        
    def init_ui(self):
        # 创建内容编辑器界面
        self.layout = QVBoxLayout()
        
        # 添加章节标题输入
        self.title_edit = QLineEdit()
        self.layout.addWidget(QLabel("章节标题"))
        self.layout.addWidget(self.title_edit)
        
        # 内容编辑区域
        self.content_edit = QTextEdit()
        self.layout.addWidget(self.content_edit)
        
        # 添加字数统计
        self.word_count_label = QLabel("字数：0")
        self.content_edit.textChanged.connect(self.update_word_count)
        self.layout.addWidget(self.word_count_label)
        
        # 保存按钮
        self.save_btn = QPushButton("保存修改")
        self.save_btn.clicked.connect(self.save_changes)
        self.layout.addWidget(self.save_btn)
        
        self.setLayout(self.layout)
        
    def update_word_count(self):
        text = self.content_edit.toPlainText()
        self.word_count_label.setText(f"字数：{len(text)}")
        
    def save_changes(self):
        """保存修改后的内容"""
        try:
            # 获取修改后的内容
            modified_content = self.content_edit.toPlainText()
            
            # 参数验证
            if not modified_content.strip():
                raise ValueError("内容不能为空")
            
            # 保存到数据库
            db = DatabaseManager('novel_writer.db')
            db.save_chapter(
                project_id=self.project_id,
                chapter_index=self.chapter_index,
                content=modified_content
            )
            
            # 提示保存成功
            QMessageBox.information(self, "保存成功", "章节内容已成功保存！")
            
        except ValueError as e:
            QMessageBox.warning(self, "保存失败", str(e))
        except sqlite3.Error as e:
            QMessageBox.critical(self, "数据库错误", f"保存章节内容时发生数据库错误：{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "未知错误", f"保存章节内容时发生未知错误：{str(e)}")