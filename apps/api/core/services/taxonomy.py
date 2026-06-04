"""Catalog taxonomy resolution services."""

from __future__ import annotations

from core.models import Category, Tag


class TaxonomyResolutionService:
    """Resolve hierarchical catalog taxonomy references."""

    def resolve_category(
        self,
        category_name: str | list[str] | None,
    ) -> Category | None:
        """Resolve a category from a flat name or hierarchical path."""
        if not category_name:
            return None

        category_path = (
            [category_name] if isinstance(category_name, str) else category_name
        )

        category = None
        parent = None
        for category_part in category_path:
            category = Category.objects.filter(name=category_part).first()
            if not category:
                category = (
                    parent.add_child(name=category_part)
                    if parent
                    else Category.add_root(name=category_part)
                )
            parent = category
        return category

    def resolve_update_category(
        self,
        category_name: str | list[str] | None,
    ) -> tuple[Category | None, bool]:
        """Resolve the category update and whether it should replace current value."""
        if category_name is None:
            return None, False
        if category_name == "":
            return None, True
        return self.resolve_category(category_name), True

    def resolve_tags(self, tags: list[str] | list[list[str]]) -> list[Tag]:
        """Resolve flat or hierarchical tag inputs to persisted tags."""
        tag_objects = []
        for tag_entry in tags:
            tag_path = [tag_entry] if isinstance(tag_entry, str) else tag_entry

            parent = None
            last_tag = None
            for tag_part in tag_path:
                tag = Tag.objects.filter(name=tag_part).first()
                if not tag:
                    tag = (
                        parent.add_child(name=tag_part)
                        if parent
                        else Tag.add_root(name=tag_part)
                    )
                parent = tag
                last_tag = tag

            if last_tag:
                tag_objects.append(last_tag)
        return tag_objects

    def resolve_update_tags(
        self,
        tags: list[str] | list[list[str]] | None,
    ) -> list[Tag] | None:
        """Resolve flat or hierarchical tag inputs for metadata updates."""
        if tags is None:
            return None
        return self.resolve_tags(tags)
