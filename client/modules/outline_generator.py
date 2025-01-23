import openai
import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QListWidget, QLabel, QPushButton

class OutlineGenerator:
    def __init__(self, db_conn, api_key):
        self.db = db_conn
        openai.api_key = api_key
        openai.api_base = "https://api.openai.com/v1"  # 或者使用兼容API的地址
        
    def generate_outline(self, project_id, theme, style, topic):
        """生成小说大纲"""
        # 参数验证
        if not all([project_id, theme, style, topic]):
            raise ValueError("缺少必要的参数")
        
        try:
            # 构造提示词
            prompt = f"请根据以下要求生成小说大纲：\n题材：{theme}\n风格：{style}\n主题：{topic}\n"
            prompt += "请生成包含以下内容的大纲：\n1. 故事主线\n2. 章节划分（至少5章）\n3. 主要人物设定\n4. 关键情节点"
            
            # 调用OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个专业的小说创作助手"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # 解析响应
            outline = self._parse_outline(response['choices'][0]['message']['content'])
            
            # 保存大纲到数据库
            self._save_outline(project_id, outline)
            return outline
        
        except Exception as e:
            print(f"生成大纲失败: {e}")
            raise
        
    def _parse_outline(self, content):
        """
        解析AI生成的大纲内容
        :param content: AI生成的原始内容
        :return: 结构化的大纲字典
        """
        # 这里可以根据实际返回格式进行调整
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 如果返回的不是JSON格式，进行手动解析
            sections = content.split("\n\n")
            outline = {
                'main_storyline': sections[0].replace("故事主线：", "").strip(),
                'chapters': [c.strip() for c in sections[1].split("\n")[1:]],
                'characters': [c.strip() for c in sections[2].split("\n")[1:]],
                'key_points': [c.strip() for c in sections[3].split("\n")[1:]]
            }
            return outline
        
    def _save_outline(self, project_id, outline):
        """
        保存大纲到数据库
        :param project_id: 项目ID
        :param outline: 大纲内容
        """
        # 这里实现数据库保存逻辑
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO outlines (project_id, content)
            VALUES (?, ?)
        """, (project_id, json.dumps(outline)))
        self.db.commit()

class OutlineEditor(QWidget):
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.init_ui()
        
    def init_ui(self):
        # 创建大纲编辑器界面
        self.layout = QVBoxLayout()
        
        # 故事主线编辑
        self.storyline_edit = QTextEdit()
        self.layout.addWidget(QLabel("故事主线"))
        self.layout.addWidget(self.storyline_edit)
        
        # 章节列表
        self.chapter_list = QListWidget()
        self.layout.addWidget(QLabel("章节划分"))
        self.layout.addWidget(self.chapter_list)
        
        # 保存按钮
        self.save_btn = QPushButton("保存修改")
        self.save_btn.clicked.connect(self.save_changes)
        self.layout.addWidget(self.save_btn)
        
        self.setLayout(self.layout)
        
    def save_changes(self):
        # 保存修改后的大纲
        modified_outline = {
            'main_storyline': self.storyline_edit.toPlainText(),
            'chapters': [self.chapter_list.item(i).text() 
                        for i in range(self.chapter_list.count())]
        }
        # ... 保存到数据库的实现 ... 