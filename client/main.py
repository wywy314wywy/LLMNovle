import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
from client.modules.outline_generator import OutlineGenerator, OutlineEditor
from client.modules.content_generator import ContentGenerator, ContentEditor
from client.database import DatabaseManager
from client.config import ConfigManager

class MainWindow(QMainWindow):
    def __init__(self, db, config, parent=None):
        super().__init__(parent)
        try:
            # 提前验证核心配置
            assert config.get_openai_config().get('api_key'), "OpenAI API密钥未配置"
            assert config.get_generation_config('outline'), "大纲生成配置缺失"
            assert config.get_generation_config('content'), "内容生成配置缺失"
            
            self.db = db
            self.config = config
            self.init_ui()
            self.outline_gen = OutlineGenerator(self.db.conn)
            self.content_gen = ContentGenerator(self.db.conn)
        except Exception as e:
            QMessageBox.critical(None, "启动失败", f"关键配置校验失败: {str(e)}")
            sys.exit(1)
        
    def init_ui(self):
        self.setWindowTitle("小说创作助手")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建主界面
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 添加大纲编辑器
        self.outline_editor = OutlineEditor(
            project_id=1, 
            db_conn=self.db.conn,
            config=self.config
        )
        self.tabs.addTab(self.outline_editor, "大纲编辑")
        
        # 添加内容编辑器
        self.content_editor = ContentEditor(project_id=1, chapter_index=1)
        self.tabs.addTab(self.content_editor, "内容编辑")
        
        # 添加状态栏
        self.statusBar().showMessage("就绪")

def main():
    app = QApplication(sys.argv)
    
    # 初始化数据库连接
    db = DatabaseManager('novel_writer.db')
    
    # 加载配置文件
    config = ConfigManager('config.json')
    
    # 创建主窗口
    window = MainWindow(db, config)
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 