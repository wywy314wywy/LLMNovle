import json
import sqlite3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QListWidget, QLabel, QPushButton, QMessageBox, QLineEdit, QProgressDialog, QTextBrowser
from PyQt5.QtCore import Qt
import openai
from client.config import Config
from client.database import DatabaseManager
from PyQt5.QtWidgets import QApplication
from markdown2 import markdown
import time
from PyQt5.QtGui import QTextCursor

class OutlineGenerator:
    def __init__(self, db_conn):
        self.db = db_conn
        self.config = Config()
        openai_config = self.config.get_openai_config()
        openai.api_key = openai_config.get("api_key")
        openai.api_base = openai_config.get("api_base")
        
    def generate_outline(self, project_id, theme, style, topic):
        """生成小说大纲"""
        progress_dialog = None
        cancel_flag = False  # 新增取消状态标志
        try:
            # 参数验证
            if not all([project_id, theme, style, topic]):
                raise ValueError("缺少必要的参数")
            
            # 构造提示词
            prompt = f"请根据以下要求生成小说大纲：\n题材：{theme}\n风格：{style}\n主题：{topic}\n"
            prompt += "请生成包含以下内容的大纲：\n1. 故事主线\n2. 章节划分（至少5章）\n3. 主要人物设定\n4. 关键情节点"
            
            # 使用配置中的参数
            generation_config = self.config.get_generation_config("outline")
            
            # 创建进度对话框
            progress_dialog = QProgressDialog("正在生成大纲...", "取消", 0, 0, None)  # 使用None作为父窗口
            progress_dialog.setWindowTitle("生成进度")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.show()
            
            # 流式请求处理优化
            output_text = ""
            response_stream = None  # 将response对象提取到变量中
            try:
                response_stream = openai.ChatCompletion.create(
                    model=self.config.get_openai_config().get("model"),
                    messages=[
                        {"role": "system", "content": "你是一个专业的小说创作助手"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=generation_config.get("temperature"),
                    max_tokens=generation_config.get("max_tokens"),
                    stream=True
                )

                for chunk in response_stream:
                    if cancel_flag:  # 使用标志位代替直接判断progress_dialog
                        break
                    if chunk.choices[0].delta.get("content"):
                        output_text += chunk.choices[0].delta["content"]
                        QApplication.processEvents()

            finally:
                # 确保流式连接关闭
                if response_stream is not None:
                    response_stream.close()

            # 统一处理取消逻辑
            if cancel_flag or (progress_dialog and progress_dialog.wasCanceled()):
                raise Exception("用户取消操作")
            
            # 解析并保存大纲
            outline = self._parse_outline(output_text)
            self._save_outline(project_id, outline)
            return outline
        
        except Exception as e:
            if isinstance(e, openai.error.APIError):
                error_msg = f"API错误: {str(e)}"
            elif "用户取消操作" in str(e):
                error_msg = None  # 用户主动取消不需要提示
            else:
                error_msg = f"生成大纲时发生错误：{str(e)}"
            
            if error_msg:
                QMessageBox.critical(None, "生成失败", error_msg)
            return None  # 返回None而不是抛出异常
        finally:
            if progress_dialog:
                progress_dialog.close()
        
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
    def __init__(self, project_id, db_conn, config, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.generator = OutlineGenerator(db_conn)
        self.config = config  # 确保config被正确设置
        self.init_ui()
        
    def init_ui(self):
        # 创建大纲编辑器界面
        self.layout = QVBoxLayout()
        
        # 故事主线编辑
        self.storyline_edit = QTextBrowser()
        self.storyline_edit.setOpenExternalLinks(True)
        self.storyline_edit.setReadOnly(False)
        self.layout.addWidget(QLabel("故事主线"))
        self.layout.addWidget(self.storyline_edit)
        
        # 章节列表
        self.chapter_list = QListWidget()
        self.layout.addWidget(QLabel("章节划分"))
        self.layout.addWidget(self.chapter_list)
        
        # 添加生成大纲按钮
        self.generate_btn = QPushButton("AI生成大纲")
        self.generate_btn.clicked.connect(self.generate_outline)
        self.layout.addWidget(self.generate_btn)
        
        # 添加主题输入框
        self.theme_input = QLineEdit()
        self.layout.addWidget(QLabel("题材"))
        self.layout.addWidget(self.theme_input)
        
        # 添加风格输入框
        self.style_input = QLineEdit()
        self.layout.addWidget(QLabel("风格"))
        self.layout.addWidget(self.style_input)
        
        # 添加主题输入框
        self.topic_input = QLineEdit()
        self.layout.addWidget(QLabel("主题"))
        self.layout.addWidget(self.topic_input)
        
        # 添加保存按钮
        self.save_btn = QPushButton("保存大纲")
        self.save_btn.clicked.connect(self.save_outline)
        self.layout.addWidget(self.save_btn)
        
        # 添加对话界面
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.layout.addWidget(QLabel("AI对话"))
        self.layout.addWidget(self.chat_history)
        
        # 添加用户输入框
        self.user_input = QLineEdit()
        self.user_input.returnPressed.connect(self.send_user_input)
        self.layout.addWidget(self.user_input)
        
        # 初始化对话历史
        self.conversation = [
            {"role": "system", "content": "你是一个专业的小说创作助手"}
        ]
        
        # 设置布局
        self.setLayout(self.layout)
        
    def generate_outline(self):
        """触发AI生成大纲"""
        theme = self.theme_input.text().strip()
        style = self.style_input.text().strip()
        topic = self.topic_input.text().strip()
        
        if not all([theme, style, topic]):
            QMessageBox.warning(self, "输入不完整", "请填写题材、风格和主题")
            return
            
        try:
            # 调用生成器生成大纲
            outline = self.generator.generate_outline(
                project_id=self.project_id,
                theme=theme,
                style=style,
                topic=topic
            )
            
            # 更新界面显示
            self.update_storyline(outline.get('main_storyline', ''))
            self.update_chapters(outline.get('chapters', []))
            
            QMessageBox.information(self, "生成成功", "大纲已成功生成！")
            
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成大纲时发生错误：{str(e)}")
            
    def save_outline(self):
        """保存当前大纲"""
        try:
            # 获取当前内容
            outline = {
                'main_storyline': self.storyline_edit.toPlainText(),
                'chapters': [self.chapter_list.item(i).text() 
                           for i in range(self.chapter_list.count())]
            }
            
            # 保存到数据库
            self.generator._save_outline(self.project_id, outline)
            QMessageBox.information(self, "保存成功", "大纲已成功保存！")
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存大纲时发生错误：{str(e)}")
            
    def send_user_input(self):
        """处理用户输入"""
        user_text = self.user_input.text().strip()
        if not user_text:
            return
            
        # 显示用户输入
        self.chat_history.append(f"你：{user_text}")
        self.user_input.clear()
        
        # 添加到对话历史
        self.conversation.append({"role": "user", "content": user_text})
        
        # 获取AI回复
        self.get_ai_response()
        
    def get_ai_response(self):
        """获取AI回复"""
        try:
            # 确保使用self.config
            response = openai.ChatCompletion.create(
                model=self.config.get_openai_config().get("model"),
                messages=self.conversation,
                stream=True
            )
            
            ai_response = ""
            last_update_time = time.time()
            buffer = ""
            
            for chunk in response:
                if chunk.choices[0].delta.get("content"):
                    buffer += chunk.choices[0].delta["content"]
                    
                    # 每0.1秒更新一次显示，或者当遇到标点符号时
                    if (time.time() - last_update_time > 0.1 or 
                        chunk.choices[0].delta["content"] in {"。", "！", "？", "，", "\n"}):
                        ai_response += buffer
                        self.chat_history.moveCursor(QTextCursor.End)
                        self.chat_history.insertPlainText(buffer)
                        self.chat_history.moveCursor(QTextCursor.End)
                        buffer = ""
                        last_update_time = time.time()
                        QApplication.processEvents()
            
            # 处理剩余的buffer内容
            if buffer:
                ai_response += buffer
                self.chat_history.moveCursor(QTextCursor.End)
                self.chat_history.insertPlainText(buffer)
                self.chat_history.moveCursor(QTextCursor.End)
                QApplication.processEvents()
            
            # 添加到对话历史
            self.conversation.append({"role": "assistant", "content": ai_response})
            
        except Exception as e:
            QMessageBox.critical(self, "对话失败", f"与AI对话时发生错误：{str(e)}")
            
    def update_storyline(self, content):
        """更新故事主线显示"""
        # 将Markdown转换为HTML
        html_content = markdown(content)
        self.storyline_edit.setHtml(html_content)
        
    def update_chapters(self, chapters):
        """更新章节列表显示"""
        self.chapter_list.clear()  # 先清空现有内容
        for chapter in chapters:
            self.chapter_list.addItem(chapter)  # 使用addItem添加每个章节 