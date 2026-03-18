from typing import Any, Dict, List

from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndexEntity
from src.python.elasticsearch.application.schemas.responses.indices.index_detail_res import (
    IndexAliasRes,
    IndexDetailRes,
    IndexDetailSummaryRes,
    IndexMappingFieldRes,
    IndexSettingRes,
    IndexStatsRes,
)


class IndexDetailMapper:
    @staticmethod
    def to_response(
        index_info: IndexEntity,
        settings_response: Dict[str, Any],
        mappings_response: Dict[str, Any],
        aliases_response: Dict[str, Any],
        stats_response: Dict[str, Any],
    ) -> IndexDetailRes:
        index_name = index_info.index

        summary = IndexDetailSummaryRes(
            index=index_info.index,
            uuid=index_info.uuid,
            health=index_info.health,
            status=index_info.status,
            pri=index_info.pri,
            rep=index_info.rep,
            docs_count=index_info.docs_count,
            docs_deleted=index_info.docs_deleted,
            store_size=index_info.store_size,
            pri_store_size=index_info.pri_store_size,
            dataset_size=index_info.dataset_size,
        )

        raw_settings = (
            settings_response.get(index_name, {})
            .get("settings", {})
        )
        settings = [
            IndexSettingRes(key=key, value=str(value))
            for key, value in sorted(raw_settings.items(), key=lambda item: item[0])
        ]

        raw_aliases = (
            aliases_response.get(index_name, {})
            .get("aliases", {})
        )
        aliases: List[IndexAliasRes] = []
        for alias_name, alias_value in sorted(raw_aliases.items(), key=lambda item: item[0]):
            aliases.append(
                IndexAliasRes(
                    name=alias_name,
                    is_write_index=bool(alias_value.get("is_write_index", False)),
                    filter=IndexDetailMapper._stringify_json(alias_value.get("filter")),
                    routing_index=alias_value.get("index_routing"),
                    routing_search=alias_value.get("search_routing"),
                )
            )

        raw_mappings = (
            mappings_response.get(index_name, {})
            .get("mappings", {})
            .get("properties", {})
        )
        mappings = IndexDetailMapper._build_mapping_fields(raw_mappings)

        indices_stats = stats_response.get("indices", {}).get(index_name, {})
        total_stats = indices_stats.get("total", {})
        primaries_stats = indices_stats.get("primaries", {})

        stats = IndexStatsRes(
            docs_count=int(total_stats.get("docs", {}).get("count", 0) or 0),
            docs_deleted=int(total_stats.get("docs", {}).get("deleted", 0) or 0),
            store_size_in_bytes=int(total_stats.get("store", {}).get("size_in_bytes", 0) or 0),
            primary_store_size_in_bytes=int(
                primaries_stats.get("store", {}).get("size_in_bytes", 0) or 0
            ),
            search_query_total=int(
                total_stats.get("search", {}).get("query_total", 0) or 0
            ),
            indexing_index_total=int(
                total_stats.get("indexing", {}).get("index_total", 0) or 0
            ),
        )

        return IndexDetailRes(
            summary=summary,
            aliases=aliases,
            settings=settings,
            mappings=mappings,
            stats=stats,
        )

    @staticmethod
    def _build_mapping_fields(properties: Dict[str, Any], prefix: str = "") -> List[IndexMappingFieldRes]:
        fields: List[IndexMappingFieldRes] = []

        for field_name, field_value in sorted(properties.items(), key=lambda item: item[0]):
            full_name = f"{prefix}.{field_name}" if prefix else field_name
            field_type = field_value.get("type", "object")

            child_properties = field_value.get("properties", {})
            nested_children = IndexDetailMapper._build_mapping_fields(child_properties, full_name)

            multi_fields = field_value.get("fields", {})
            multi_children = []
            for multi_name, multi_value in sorted(multi_fields.items(), key=lambda item: item[0]):
                multi_full_name = f"{full_name}.{multi_name}"
                multi_children.append(
                    IndexMappingFieldRes(
                        name=multi_full_name,
                        type=multi_value.get("type", "object"),
                        children=[],
                    )
                )

            children = nested_children + multi_children

            fields.append(
                IndexMappingFieldRes(
                    name=full_name,
                    type=field_type,
                    children=children,
                )
            )

        return fields

    @staticmethod
    def _stringify_json(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value

        import json
        return json.dumps(value, ensure_ascii=False, sort_keys=True)