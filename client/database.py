import sqlite3
from typing import Optional, Dict, List
from datetime import datetime
import json

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._check_and_update_schema()

    def _check_and_update_schema(self):
        """检查并更新数据库schema"""
        cursor = self.conn.cursor()
        
        # 创建版本控制表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 获取当前版本
        cursor.execute("SELECT version FROM db_version ORDER BY version DESC LIMIT 1")
        result = cursor.fetchone()
        current_version = result[0] if result else 0
        
        # 执行必要的schema更新
        if current_version < 1:
            self._create_tables_v1()
            cursor.execute("INSERT INTO db_version (version) VALUES (1)")
            self.conn.commit()
        
        # 未来版本更新可以这样添加
        # if current_version < 2:
        #     self._update_schema_v2()
        #     cursor.execute("INSERT INTO db_version (version) VALUES (2)")
        #     self.conn.commit()

    def _create_tables_v1(self):
        """创建初始表结构（版本1）"""
        cursor = self.conn.cursor()
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 项目表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
            author TEXT,
            status TEXT CHECK(status IN ('draft', 'in_progress', 'completed')) DEFAULT 'draft',
            theme TEXT,
            style TEXT,
            topic TEXT,
            ai_model TEXT,
            settings TEXT
        )
        """)
        
        # 大纲表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS outlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 章节表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            chapter_index INTEGER NOT NULL,
            title TEXT,
            content TEXT,
            status TEXT CHECK(status IN ('not_started', 'generating', 'pending_review', 'completed')) DEFAULT 'not_started',
            ai_params TEXT,
            last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 角色表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            personality TEXT,
            appearance TEXT,
            background TEXT,
            relationships TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 审核记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            review_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            review_type TEXT CHECK(review_type IN ('plot', 'character', 'style', 'logic')),
            result TEXT,
            issues TEXT,
            suggestions TEXT,
            status TEXT CHECK(status IN ('pending', 'resolved')),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_id ON outlines(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chapter_project ON chapters(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_character_project ON characters(project_id)")
        
        self.conn.commit()

    # 项目相关操作
    def create_project(self, name: str, author: str, theme: str, style: str, topic: str) -> int:
        """创建新项目"""
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO projects (name, author, theme, style, topic)
        VALUES (?, ?, ?, ?, ?)
        """, (name, author, theme, style, topic))
        self.conn.commit()
        return cursor.lastrowid

    def get_project(self, project_id: int) -> Optional[Dict]:
        """获取项目详情"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row))
        return None

    def update_project(self, project_id: int, **kwargs) -> bool:
        """更新项目信息"""
        if not kwargs:
            return False
        
        valid_fields = ['name', 'author', 'theme', 'style', 'topic', 'status']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not updates:
            return False
        
        try:
            cursor = self.conn.cursor()
            set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
            values = tuple(updates.values()) + (project_id,)
            
            cursor.execute(f"""
                UPDATE projects 
                SET {set_clause}, last_modified = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"更新项目失败: {e}")
            return False

    def delete_project(self, project_id: int) -> bool:
        """删除项目及其所有相关数据"""
        try:
            cursor = self.conn.cursor()
            # 开启事务
            cursor.execute("BEGIN TRANSACTION")
            
            # 删除相关数据
            cursor.execute("DELETE FROM outlines WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM characters WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM reviews WHERE project_id = ?", (project_id,))
            
            # 删除项目
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"删除项目失败: {e}")
            return False

    # 大纲相关操作
    def save_outline(self, project_id: int, content: Dict) -> int:
        """保存大纲"""
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO outlines (project_id, content)
        VALUES (?, ?)
        """, (project_id, json.dumps(content)))
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_outline(self, project_id: int) -> Optional[Dict]:
        """获取项目最新大纲"""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT content FROM outlines 
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """, (project_id,))
        result = cursor.fetchone()
        return json.loads(result[0]) if result else None

    # 章节相关操作
    def save_chapter(self, project_id: int, chapter_index: int, content: str, title: str = None) -> int:
        """保存章节内容"""
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO chapters (project_id, chapter_index, title, content)
        VALUES (?, ?, ?, ?)
        """, (project_id, chapter_index, title, content))
        self.conn.commit()
        return cursor.lastrowid

    def get_chapter(self, project_id: int, chapter_index: int) -> Optional[Dict]:
        """获取章节内容"""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM chapters 
        WHERE project_id = ? AND chapter_index = ?
        ORDER BY last_modified DESC
        LIMIT 1
        """, (project_id, chapter_index))
        row = cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row))
        return None

    # 其他操作方法...
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 