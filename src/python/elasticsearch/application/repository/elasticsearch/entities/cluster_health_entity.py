from typing import Dict, Optional
from pydantic import BaseModel, Field

class ClusterHealthEntity(BaseModel):
    cluster_name: str = Field(
        ...,
        title="Cluster Name",
        description="The name of the Elasticsearch cluster."
    )
    status: str = Field(
        ...,
        title="Cluster Status",
        description="Overall cluster health status. One of: green, yellow, red."
    )
    timed_out: bool = Field(
        ...,
        title="Timed Out",
        description="Indicates whether the cluster health request timed out."
    )
    number_of_nodes: int = Field(
        ...,
        title="Number of Nodes",
        description="Total number of nodes in the cluster."
    )
    number_of_data_nodes: int = Field(
        ...,
        title="Number of Data Nodes",
        description="Number of data nodes in the cluster."
    )
    active_primary_shards: int = Field(
        ...,
        title="Active Primary Shards",
        description="Number of primary shards that are active across the cluster."
    )
    active_shards: int = Field(
        ...,
        title="Active Shards",
        description="Total number of active shards (primary + replica) across the cluster."
    )
    relocating_shards: int = Field(
        ...,
        title="Relocating Shards",
        description="Number of shards currently being relocated across the cluster."
    )
    initializing_shards: int = Field(
        ...,
        title="Initializing Shards",
        description="Number of shards currently being initialized across the cluster."
    )
    unassigned_shards: int = Field(
        ...,
        title="Unassigned Shards",
        description="Number of shards that are unassigned across the cluster."
    )
    delayed_unassigned_shards: int = Field(
        ...,
        title="Delayed Unassigned Shards",
        description="Number of unassigned shards whose allocation is delayed."
    )
    number_of_pending_tasks: int = Field(
        ...,
        title="Pending Tasks",
        description="Number of pending cluster-level tasks."
    )
    number_of_in_flight_fetch: int = Field(
        ...,
        title="In-flight Fetches",
        description="Number of shard fetches currently ongoing."
    )
    active_shards_percent_as_number: float = Field(
        ...,
        title="Active Shards Percentage",
        description="Percentage of active shards in the cluster (0 to 100)."
    )