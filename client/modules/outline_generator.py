import json
import sqlite3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QListWidget, QLabel, QPushButton, QMessageBox, QLineEdit, QProgressDialog, QTextBrowser, QHBoxLayout, QGridLayout, QProgressBar
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
        
    def generate_outline(self, project_id, theme, style, topic, update_callback=None):
        """生成小说大纲"""
        progress_dialog = None
        cancel_flag = False
        try:
            # 确保配置存在
            openai_config = self.config.get_openai_config()
            if not openai_config:
                raise ValueError("OpenAI配置缺失，请检查config.json")
            
            generation_config = self.config.get_generation_config("outline")

            # 关键参数校验
            if not openai_config.get("model"):
                raise ValueError("AI模型配置缺失，请检查config.json中的openai.model设置")
            
            # 参数验证
            if not all([project_id, theme, style, topic]):
                raise ValueError("缺少必要的参数")
            
            # 构造提示词
            prompt = f"""基于以下要素创作小说大纲：
题材类型：{theme}
文学风格：{style}
核心主题：{topic}

请按照以下结构生成详细大纲（JSON格式）：
{{
    "main_storyline": {{
        "overview": "故事核心梗概（50-100字）",
        "structure": {{
            "开端": "触发事件和背景铺垫",
            "发展": "主要矛盾升级过程",
            "高潮": "故事的最高冲突点",
            "结局": "最终解决方式"
        }}
    }},
    "chapters": [
        {{
            "chapter_number": 1,
            "title": "章节标题",
            "pov": "叙事视角",
            "key_scenes": [
                {{
                    "scene_type": "对话/动作/描写",
                    "purpose": "场景作用",
                    "characters": ["参与角色"],
                    "location": "场景地点"
                }}
            ],
            "word_count_target": 2500
        }}
    ],
    "characters": [
        {{
            "name": "角色姓名",
            "archetype": "角色原型（如英雄、导师等）",
            "motivation": "核心动机",
            "arc": "角色成长弧线",
            "appearance": "外貌特征",
            "key_relationships": ["与其他角色的关系"]
        }}
    ],
    "worldbuilding": {{
        "time_period": "时代背景",
        "locations": {{
            "核心场景1": "场景特征与象征意义"
        }},
        "magic_tech_systems": "特殊设定（如存在）",
        "cultural_rules": "社会规则与文化特征"
    }},
    "thematic_elements": {{
        "central_conflicts": "核心矛盾",
        "symbolism": "核心意象",
        "moral_questions": "探讨的道德问题"
    }}
}}"""
            
            # 流式请求处理优化
            output_text = ""
            response_stream = None
            try:
                response_stream = openai.ChatCompletion.create(
                    model=openai_config.get("model"),
                    messages=[
                        {"role": "system", "content": "你是一个专业的小说创作助手"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=generation_config.get("temperature"),
                    max_tokens=generation_config.get("max_tokens"),
                    stream=True
                )

                for chunk in response_stream:
                    if cancel_flag:
                        break
                    if chunk.choices[0].delta.get("content"):
                        content = chunk.choices[0].delta["content"]
                        output_text += content
                        if update_callback:  # 如果有回调函数，则调用
                            update_callback(content)
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
        try:
            # 尝试提取Markdown中的JSON代码块
            if "```json" in content:
                # 提取json代码块内容
                json_content = content.split("```json")[1].split("```")[0].strip()
                outline = json.loads(json_content)
            elif "```" in content:
                # 处理不带json标记的代码块
                json_content = content.split("```")[1].split("```")[0].strip()
                outline = json.loads(json_content)
            else:
                # 直接解析整个内容
                outline = json.loads(content)
            
            # 验证必要字段
            required_fields = ['main_storyline', 'chapters']
            for field in required_fields:
                if field not in outline:
                    raise ValueError(f"大纲缺少必要字段: {field}")
                
            # 确保数据结构完整
            if not isinstance(outline['main_storyline'], dict):
                outline['main_storyline'] = {}
            if not isinstance(outline['chapters'], list):
                outline['chapters'] = []
            
            return outline
        
        except json.JSONDecodeError as e:
            # 如果JSON解析失败，尝试提取关键信息
            try:
                # 提取故事主线
                main_storyline = {}
                if "故事主线" in content:
                    story_parts = content.split("故事主线：")[1].split("\n\n")[0]
                    main_storyline = {
                        'overview': story_parts.split("\n")[0].strip(),
                        'structure': {
                            '开端': story_parts.split("\n")[1].replace("开端：", "").strip(),
                            '发展': story_parts.split("\n")[2].replace("发展：", "").strip(),
                            '高潮': story_parts.split("\n")[3].replace("高潮：", "").strip(),
                            '结局': story_parts.split("\n")[4].replace("结局：", "").strip()
                        }
                    }
                
                # 提取章节列表
                chapters = []
                if "章节列表" in content:
                    chapter_lines = content.split("章节列表：")[1].split("\n\n")[0].split("\n")
                    chapters = [line.strip() for line in chapter_lines if line.strip()]
                
                return {
                    'main_storyline': main_storyline,
                    'chapters': chapters
                }
            
            except Exception as e:
                raise ValueError(f"解析大纲失败: {str(e)}")
        
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
        self.config = config
        self.init_ui()
        
    def init_ui(self):
        # 主布局改为水平布局
        main_layout = QHBoxLayout()
        
        # 左侧大纲编辑区域
        left_panel = QVBoxLayout()
        
        # 输入区域网格布局
        input_grid = QGridLayout()
        input_grid.addWidget(QLabel("题材"), 0, 0)
        self.theme_input = QLineEdit()
        input_grid.addWidget(self.theme_input, 0, 1)
        input_grid.addWidget(QLabel("风格"), 1, 0)
        self.style_input = QLineEdit()
        input_grid.addWidget(self.style_input, 1, 1)
        input_grid.addWidget(QLabel("主题"), 2, 0)
        self.topic_input = QLineEdit()
        input_grid.addWidget(self.topic_input, 2, 1)
        
        # 大纲显示区域
        self.storyline_edit = QTextBrowser()
        self.chapter_list = QListWidget()
        
        # 右侧AI交互区域
        right_panel = QVBoxLayout()
        
        # 实时输出窗口
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMinimumWidth(400)
        
        # 进度状态栏
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度模式
        self.progress_bar.hide()
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成大纲")
        self.generate_btn.clicked.connect(self.generate_outline)
        self.save_btn = QPushButton("保存大纲")
        self.save_btn.clicked.connect(self.save_outline)
        
        # 组装左侧布局
        left_panel.addLayout(input_grid)
        left_panel.addWidget(QLabel("故事主线"))
        left_panel.addWidget(self.storyline_edit)
        left_panel.addWidget(QLabel("章节列表"))
        left_panel.addWidget(self.chapter_list)
        left_panel.addLayout(btn_layout)
        
        # 组装右侧布局
        right_panel.addWidget(QLabel("AI工作台"))
        right_panel.addWidget(self.output_console)
        right_panel.addWidget(self.progress_bar)
        
        # 主布局组合
        main_layout.addLayout(left_panel, 60)  # 左侧占60%宽度
        main_layout.addLayout(right_panel, 40)  # 右侧占40%宽度
        
        # 按钮添加到布局
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.save_btn)
        
        self.setLayout(main_layout)
        
    def generate_outline(self):
        """触发AI生成大纲"""
        self.output_console.clear()
        self.progress_bar.show()  # 使用主界面进度条替代弹窗
        
        try:
            theme = self.theme_input.text().strip()
            style = self.style_input.text().strip()
            topic = self.topic_input.text().strip()
            
            if not all([theme, style, topic]):
                QMessageBox.warning(self, "输入不完整", "请填写题材、风格和主题")
                return
            
            # 显示实时输出
            def update_output(content):
                self.output_console.moveCursor(QTextCursor.End)
                self.output_console.insertPlainText(content)
                QApplication.processEvents()
            
            # 调用生成器生成大纲
            outline = self.generator.generate_outline(
                project_id=self.project_id,
                theme=theme,
                style=style,
                topic=topic,
                update_callback=update_output  # 实时更新到工作台
            )
            
            # 更新界面显示
            self.update_storyline(outline.get('main_storyline', ''))
            self.update_chapters(outline.get('chapters', []))
            
            QMessageBox.information(self, "生成成功", "大纲已成功生成！")
            
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成大纲时发生错误：{str(e)}")
            
        finally:
            self.progress_bar.hide()  # 隐藏主界面进度条
        
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
            
    def update_storyline(self, data):
        """更新故事主线显示"""
        self.storyline_edit.clear()
        
        # 添加空值保护
        if not data or not isinstance(data, dict):
            return
        
        # 确保数据结构完整
        main_storyline = data.get('main_storyline', {})
        structure = main_storyline.get('structure', {})
        
        html_content = f"""
        <h3>故事梗概</h3>
        <p>{main_storyline.get('overview', '')}</p>
        <h3>故事结构</h3>
        <ul>
            <li>开端：{structure.get('开端', '')}</li>
            <li>发展：{structure.get('发展', '')}</li>
            <li>高潮：{structure.get('高潮', '')}</li>
            <li>结局：{structure.get('结局', '')}</li>
        </ul>
        """
        self.storyline_edit.setHtml(html_content)
        
    def update_chapters(self, chapters):
        """更新章节列表显示"""
        self.chapter_list.clear()  # 先清空现有内容
        for chapter in chapters:
            self.chapter_list.addItem(chapter)  # 使用addItem添加每个章节 

    def _update_preview(self, content):
        """动态更新预览内容"""
        # 尝试解析已生成的部分内容
        if "故事主线" in content:
            parts = content.split("故事主线：")[1].split("\n\n")[0]
            self.storyline_edit.setPlainText(parts)
        
        if "章节划分" in content:
            chapters = [line.strip() for line in content.split("章节划分：")[1].split("\n") if line.strip()]
            self.chapter_list.clear()
            self.chapter_list.addItems(chapters[:5])  # 先显示前5章 

    def update_characters(self, characters):
        """新增角色信息面板"""
        # 在左侧面板添加角色信息展示组件
        # ... 实现角色详细信息展示逻辑 ... 