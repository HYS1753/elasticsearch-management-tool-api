from typing import Dict, Any, List
from collections import defaultdict

from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndicesEntity
from src.python.elasticsearch.application.schemas.responses.indices.indices_res import IndicesRes, IndexInfoRes


class IndicesMapper:

    @staticmethod
    def to_response(indices_infos: IndicesEntity
                    ) -> IndicesRes:
        """
        Map IndicesEntity → IndicesRes
        """
        # 1. IndexRes 리스트 Mapping 생성
        indices = [
            IndexInfoRes(
                index=index.index,
                uuid=index.uuid,
                health=index.health,
                status=index.status,
                pri=index.pri,
                rep=index.rep,
                docs_count=index.docs_count,
                docs_deleted=index.docs_deleted,
                store_size=index.store_size,
                dataset_size=index.dataset_size,
                pri_store_size=index.pri_store_size,
            ) for index in indices_infos.indices
        ]

        return IndicesRes(
            indices=indices
        )