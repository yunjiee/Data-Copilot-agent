from pathlib import Path
from typing import Any, List, Optional, Sequence
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool

# 動態取得專案根目錄 (my-adk-project) 與套件目錄 (my_agent)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class SkillResolver:
    """專職處理 Skill 檔案路徑解析、搜尋鏈管理與內容載入的元件。"""

    DEFAULT_SEARCH_DIRS = (
        PACKAGE_ROOT / "skills",
        PROJECT_ROOT / "skills",
    )

    def __init__(
        self,
        primary_dir: Optional[Path] = None,
        fallback_dirs: Optional[Sequence[Path]] = None,
    ):
        self.search_dirs: List[Path] = []

        # 優先搜尋自訂目錄（若有指定）
        if primary_dir is not None:
            self.search_dirs.append(primary_dir.resolve())

        # 依序加入備選目錄（自動排除重複）
        fallbacks = fallback_dirs if fallback_dirs is not None else self.DEFAULT_SEARCH_DIRS
        for p in fallbacks:
            resolved = p.resolve()
            if resolved not in self.search_dirs:
                self.search_dirs.append(resolved)

    def resolve(self, skill_name: str) -> Optional[Path]:
        """依搜尋鏈解析技能檔案的真實路徑。"""
        # 1. 支援直接傳入絕對或相對實體路徑
        direct_path = Path(skill_name)
        if direct_path.is_file():
            return direct_path.resolve()
        if direct_path.is_dir():
            for fallback in ("SKILL.md", "skill.md"):
                if (direct_path / fallback).is_file():
                    return (direct_path / fallback).resolve()

        filename = skill_name if skill_name.endswith(".md") else f"{skill_name}.md"
        clean_name = skill_name[:-3] if skill_name.endswith(".md") else skill_name

        for search_dir in self.search_dirs:
            if not search_dir.is_dir():
                continue
            # (1) 直接尋找 search_dir / {skill_name}.md
            candidate = search_dir / filename
            if candidate.is_file():
                return candidate
            # (2) 支援資料夾型態 (search_dir / clean_name / SKILL.md)
            for sub_name in ("SKILL.md", "skill.md", filename):
                sub_candidate = search_dir / clean_name / sub_name
                if sub_candidate.is_file():
                    return sub_candidate
            # (3) 支援雙層巢狀目錄搜尋 (例如 skills/skills/skill-creator)
            for nested in search_dir.glob(f"**/{clean_name}"):
                if nested.is_dir():
                    for sub_name in ("SKILL.md", "skill.md", filename):
                        nested_candidate = nested / sub_name
                        if nested_candidate.is_file():
                            return nested_candidate
        return None

    def read(self, skill_name: str) -> str:
        """讀取指定技能內容，若找不到或讀取失敗則回傳友善錯誤。"""
        skill_path = self.resolve(skill_name)
        if skill_path is None:
            searched_paths = ", ".join(f"'{p}'" for p in self.search_dirs)
            return f"錯誤：找不到技能檔案 '{skill_name}'。已搜尋路徑：{searched_paths}"

        try:
            return skill_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"讀取技能檔案 '{skill_name}' 失敗：{str(e)}"

    def list_available(self, allowed_skills: Optional[Sequence[str]] = None) -> List[str]:
        """取得所有可用技能名稱（去除 .md 後綴）。"""
        if allowed_skills is not None:
            return [s[:-3] if s.endswith(".md") else s for s in allowed_skills]

        discovered: set[str] = set()
        for search_dir in self.search_dirs:
            if search_dir.is_dir():
                # 搜尋直接底下的 .md 檔
                for f in search_dir.glob("*.md"):
                    if f.name.lower() not in ("readme.md",):
                        discovered.add(f.stem)
                # 搜尋子資料夾內的 SKILL.md 或 skill.md
                for skill_file in search_dir.glob("**/SKILL.md"):
                    discovered.add(skill_file.parent.name)
                for skill_file in search_dir.glob("**/skill.md"):
                    discovered.add(skill_file.parent.name)
        return sorted(discovered)

    def save_skill(self, skill_name: str, content: str, target_dir: Optional[Path] = None) -> str:
        """建立或覆寫技能檔案。"""
        dest_dir = target_dir or (self.search_dirs[0] if self.search_dirs else PROJECT_ROOT / "skills")
        clean_name = skill_name[:-3] if skill_name.endswith(".md") else skill_name
        skill_folder = dest_dir / clean_name
        skill_folder.mkdir(parents=True, exist_ok=True)
        target_file = skill_folder / "SKILL.md"
        try:
            target_file.write_text(content, encoding="utf-8")
            return f"✅ 技能 '{clean_name}' 已成功儲存於：{target_file.resolve()}"
        except Exception as e:
            return f"❌ 儲存技能失敗：{str(e)}"


class SkillToolset(BaseToolset):
    """Google ADK SkillToolset。
    
    將本地技能 Markdown 檔案打包為 ADK Toolset，供 Agent 在需要時主動檢索與閱讀，
    避免將長篇幅技能規範直接塞入 Prompt 造成 Token 浪費。
    """

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        skills: Optional[List[str]] = None,
    ):
        """
        Args:
            skills_dir: 存放 skill 檔案的資料夾路徑，預設為專案根目錄下的 `skills`。
            skills: 此 Toolset 允許存取的 skill 檔案名稱列表（如 ["presentation_design_skill.md"]）。
                    若未指定，則預設讀取 skills_dir 下所有 .md 檔案。
        """
        super().__init__()
        self.resolver = SkillResolver(primary_dir=skills_dir)
        self.allowed_skills = skills
        self._tools: Optional[List[BaseTool]] = None

    def _build_tools(self) -> List[BaseTool]:
        """建立 Tool 函式並包裝為 ADK FunctionTool。"""
        def list_skills() -> List[str]:
            """列出目前可查詢的所有專業技能與規範手冊名稱。"""
            return self.resolver.list_available(self.allowed_skills)

        def read_skill(skill_name: str) -> str:
            """根據技能名稱讀取該專業技能的詳細手冊與設計規範內容。"""
            return self.resolver.read(skill_name.strip())

        def create_skill(skill_name: str, content: str) -> str:
            """根據技能名稱與 Markdown 規範內容，建立並儲存新的專業技能檔案。"""
            return self.resolver.save_skill(skill_name.strip(), content)

        return [FunctionTool(list_skills), FunctionTool(read_skill), FunctionTool(create_skill)]

    async def get_tools(self, readonly_context: Optional[Any] = None) -> List[BaseTool]:
        if self._tools is None:
            self._tools = self._build_tools()
        return self._tools

    async def close(self) -> None:
        self._tools = None