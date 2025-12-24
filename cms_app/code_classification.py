"""Code classification system for medical device companies.

This module enables medical device companies to organize HCPCS/CPT codes
into device categories, making it easier to find target customer lists.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config


@dataclass
class DeviceCategory:
    """Represents a device category with associated codes."""
    name: str
    description: str = ""
    codes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceCategory:
        """Create from dictionary."""
        return cls(**data)
    
    def add_code(self, code: str) -> bool:
        """Add a code to this category if not already present.
        
        Args:
            code: HCPCS/CPT code to add (will be normalized)
        
        Returns:
            True if code was added, False if already present
        """
        normalized = str(code).strip().upper()
        if normalized and normalized not in self.codes:
            self.codes.append(normalized)
            self.updated_at = datetime.now().isoformat()
            return True
        return False
    
    def remove_code(self, code: str) -> bool:
        """Remove a code from this category.
        
        Args:
            code: HCPCS/CPT code to remove (will be normalized)
        
        Returns:
            True if code was removed, False if not found
        """
        normalized = str(code).strip().upper()
        if normalized in self.codes:
            self.codes.remove(normalized)
            self.updated_at = datetime.now().isoformat()
            return True
        return False


class CodeClassificationManager:
    """Manages code classifications for device categories."""
    
    def __init__(self, file_path: Path | None = None):
        """Initialize the manager.
        
        Args:
            file_path: Path to JSON file storing classifications.
                      If None, uses default from config.
        """
        if file_path is None:
            config = Config()
            file_path = config.PROJECT_ROOT / "code_classifications.json"
        
        self.file_path = Path(file_path)
        self._categories: dict[str, DeviceCategory] = {}
        self._load()
    
    def _load(self) -> None:
        """Load classifications from JSON file."""
        if not self.file_path.exists():
            self._categories = {}
            return
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._categories = {
                name: DeviceCategory.from_dict(cat_data)
                for name, cat_data in data.items()
            }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # If file is corrupted, start fresh
            self._categories = {}
    
    def _save(self) -> None:
        """Save classifications to JSON file."""
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            name: cat.to_dict()
            for name, cat in self._categories.items()
        }
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_category(self, name: str) -> DeviceCategory | None:
        """Get a category by name.
        
        Args:
            name: Category name
        
        Returns:
            DeviceCategory if found, None otherwise
        """
        return self._categories.get(name)
    
    def get_all_categories(self) -> list[DeviceCategory]:
        """Get all categories.
        
        Returns:
            List of all DeviceCategory objects, sorted by name
        """
        return sorted(self._categories.values(), key=lambda c: c.name.lower())
    
    def add_category(self, name: str, description: str = "") -> DeviceCategory:
        """Create a new category.
        
        Args:
            name: Category name (must be unique)
            description: Category description
        
        Returns:
            Created DeviceCategory
        
        Raises:
            ValueError: If category with this name already exists
        """
        if name in self._categories:
            raise ValueError(f"Category '{name}' already exists")
        
        category = DeviceCategory(name=name, description=description)
        self._categories[name] = category
        self._save()
        return category
    
    def update_category(self, name: str, description: str | None = None) -> DeviceCategory:
        """Update an existing category.
        
        Args:
            name: Category name
            description: New description (if provided)
        
        Returns:
            Updated DeviceCategory
        
        Raises:
            KeyError: If category not found
        """
        if name not in self._categories:
            raise KeyError(f"Category '{name}' not found")
        
        category = self._categories[name]
        if description is not None:
            category.description = description
            category.updated_at = datetime.now().isoformat()
        
        self._save()
        return category
    
    def delete_category(self, name: str) -> bool:
        """Delete a category.
        
        Args:
            name: Category name
        
        Returns:
            True if deleted, False if not found
        """
        if name in self._categories:
            del self._categories[name]
            self._save()
            return True
        return False
    
    def add_code_to_category(self, category_name: str, code: str) -> bool:
        """Add a code to a category.
        
        Args:
            category_name: Category name
            code: HCPCS/CPT code to add
        
        Returns:
            True if code was added, False if already present or category not found
        """
        category = self.get_category(category_name)
        if not category:
            return False
        
        added = category.add_code(code)
        if added:
            self._save()
        return added
    
    def remove_code_from_category(self, category_name: str, code: str) -> bool:
        """Remove a code from a category.
        
        Args:
            category_name: Category name
            code: HCPCS/CPT code to remove
        
        Returns:
            True if code was removed, False if not found or category not found
        """
        category = self.get_category(category_name)
        if not category:
            return False
        
        removed = category.remove_code(code)
        if removed:
            self._save()
        return removed
    
    def get_codes_for_category(self, category_name: str) -> list[str]:
        """Get all codes for a category.
        
        Args:
            category_name: Category name
        
        Returns:
            List of codes, empty list if category not found
        """
        category = self.get_category(category_name)
        if not category:
            return []
        return category.codes.copy()
    
    def search_codes_by_category(self, category_name: str) -> list[str]:
        """Search for codes in a category (alias for get_codes_for_category).
        
        Args:
            category_name: Category name
        
        Returns:
            List of codes
        """
        return self.get_codes_for_category(category_name)
    
    def category_exists(self, name: str) -> bool:
        """Check if a category exists.
        
        Args:
            name: Category name
        
        Returns:
            True if category exists
        """
        return name in self._categories


