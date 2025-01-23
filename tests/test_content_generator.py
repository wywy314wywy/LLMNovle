import unittest
from client.database import DatabaseManager
from client.modules.content_generator import ContentGenerator

class TestContentGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 使用内存数据库进行测试
        cls.db = DatabaseManager(':memory:')
        cls.generator = ContentGenerator(cls.db, 'test_api_key')
        
    def test_content_generation_workflow(self):
        # 创建测试项目
        project_id = self.db.create_project(
            name="测试小说",
            author="测试作者",
            theme="测试题材",
            style="测试风格",
            topic="测试主题"
        )
        
        # 保存测试大纲
        outline = {
            "main_storyline": "测试故事主线",
            "chapters": ["第一章", "第二章"],
            "characters": ["测试角色A", "测试角色B"],
            "key_points": ["测试关键点1", "测试关键点2"]
        }
        self.db.save_outline(project_id, outline)
        
        # 测试章节生成
        style_params = {
            'style': '正式',
            'length': 1000
        }
        content = self.generator.generate_chapter(project_id, 1, style_params)
        
        # 验证生成结果
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 500)
        
        # 验证数据库保存
        saved_chapter = self.db.get_chapter(project_id, 1)
        self.assertIsNotNone(saved_chapter)
        self.assertEqual(saved_chapter['content'], content)

if __name__ == '__main__':
    unittest.main() 