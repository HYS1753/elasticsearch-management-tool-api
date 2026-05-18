import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, List, Any

from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus
from src.python.elasticsearch.application.services.api.dictionary_deploy_service import DictionaryDeployService
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException

@pytest.mark.unit
class TestDictionaryDeployServiceUnit:

    @pytest.fixture
    def mock_db(self):
        """Mock motor MongoDB database"""
        return MagicMock()

    @pytest.fixture
    def mock_es(self):
        """Mock Elasticsearch client"""
        return MagicMock()

    def setup_mock_repositories(self, service: DictionaryDeployService, mock_data: Dict[str, List[Dict[str, Any]]]):
        """Sets up mock methods on the service's repositories"""
        repos = {
            "user_dictionary": service.user_dict_repo,
            "decompound_dictionary": service.decompound_dict_repo,
            "synonym_dictionary": service.synonym_dict_repo,
            "correction_dictionary": service.correction_dict_repo,
            "stopword_dictionary": service.stopword_dict_repo
        }

        for name, repo in repos.items():
            docs = mock_data.get(name, [])
            
            def make_get_by_status(documents=docs):
                async def get_by_status(status: str):
                    status_docs = []
                    for d in documents:
                        if d.get("delete_yn", "N") != "N":
                            continue
                        if d.get("status") == status:
                            status_docs.append(d)
                    return status_docs
                return get_by_status

            repo.get_by_status = AsyncMock(side_effect=make_get_by_status())
            repo.update_status = AsyncMock(return_value=True)

        # Mock Cat Repo
        service.cat_repo.get_cluster_node_ips = AsyncMock(return_value=["127.0.0.1", "127.0.0.2"])

        # Mock Indices Repo
        service.indices_repo.exists_index_template = AsyncMock(return_value=False)
        service.indices_repo.put_index_template = AsyncMock()
        service.indices_repo.exists_index = AsyncMock(return_value=True)
        service.indices_repo.create_index = AsyncMock()
        service.indices_repo.analyze_text = AsyncMock(return_value={
            "tokens": [{"token": "테스트", "start_offset": 0, "end_offset": 3, "type": "word", "position": 0}]
        })
        service.indices_repo.delete_index_safe = AsyncMock()

    @pytest.mark.asyncio
    async def test_get_all_dictionary_lines_formatting(self, mock_db, mock_es):
        """Test formatting and deduplication across different dictionaries"""
        mock_data = {
            "user_dictionary": [
                {"word": "사용자사전1", "delete_yn": "N", "status": DictionaryStatus.APPLIED},
                {"word": "사용자사전2", "delete_yn": "N", "status": DictionaryStatus.APPROVED},
                {"word": "사용자사전1", "delete_yn": "N", "status": DictionaryStatus.APPROVED} # Duplicate
            ],
            "decompound_dictionary": [
                {"compound_word": "고속도로", "components": ["고속", "도로"], "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ],
            "synonym_dictionary": [
                {"synonyms": ["노트북", "컴퓨터"], "delete_yn": "N", "status": DictionaryStatus.APPLIED}
            ],
            "correction_dictionary": [
                {"incorrect": "외않되", "corrected": ["왜안돼"], "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ],
            "stopword_dictionary": [
                {"word": "그리고", "delete_yn": "N", "status": DictionaryStatus.APPLIED}
            ]
        }

        service = DictionaryDeployService(mock_db, mock_es)
        self.setup_mock_repositories(service, mock_data)
        
        noun_lines, synonym_lines, stop_lines, approved_docs = await service._get_all_dictionary_lines()

        # Check nouns (user_dictionary + decompound_dictionary)
        assert "사용자사전1" in noun_lines
        assert "사용자사전2" in noun_lines
        assert "고속도로,고속,도로" in noun_lines
        assert len(noun_lines) == 3 # Deduplicated "사용자사전1"

        # Check synonyms (synonym_dictionary + correction_dictionary)
        assert "노트북,컴퓨터" in synonym_lines
        assert "외않되 => 왜안돼" in synonym_lines
        assert len(synonym_lines) == 2

        # Check stopwords
        assert "그리고" in stop_lines
        assert len(stop_lines) == 1

        # Check approved tracking
        assert len(approved_docs) == 3 # user_dict, decompound_dict, correction_dict each have APPROVED entries
        collections_with_approved = [g["collection"] for g in approved_docs]
        assert "user_dictionary" in collections_with_approved
        assert "decompound_dictionary" in collections_with_approved
        assert "correction_dictionary" in collections_with_approved

    @pytest.mark.asyncio
    async def test_get_cluster_node_ips(self, mock_db, mock_es):
        """Test getting node IPs from cat_repo"""
        service = DictionaryDeployService(mock_db, mock_es)
        service.cat_repo.get_cluster_node_ips = AsyncMock(return_value=["127.0.0.1", "127.0.0.2"])
        
        ips = await service.cat_repo.get_cluster_node_ips()
        assert ips == ["127.0.0.1", "127.0.0.2"]

    @pytest.mark.asyncio
    @patch("paramiko.SSHClient")
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.settings")
    async def test_validate_dictionaries_success(self, mock_settings, mock_ssh_class, mock_db, mock_es):
        """Test the whole validation process successfully mocks SFTP and ES commands"""
        # Configure mock settings
        mock_settings.SSH_DICTIONARY_DIR = "/etc/elasticsearch/analysis"
        mock_settings.GET_SSH_SERVERS = [
            {"host": "127.0.0.1", "port": 22, "username": "elastic", "key_path": "/path/to/id_rsa"},
            {"host": "127.0.0.2", "port": 22, "username": "elastic", "key_path": "/path/to/id_rsa"}
        ]

        service = DictionaryDeployService(mock_db, mock_es)

        # Set up mock repositories
        mock_data = {
            "user_dictionary": [
                {"word": "새로운단어", "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ],
            "decompound_dictionary": [],
            "synonym_dictionary": [],
            "correction_dictionary": [],
            "stopword_dictionary": []
        }
        self.setup_mock_repositories(service, mock_data)

        # Set up mock SSH and SFTP
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh
        
        # Execute validation
        res = await service.validate_dictionaries()

        assert res["status"] == "SUCCESS"
        assert res["nouns_count"] == 1
        assert "127.0.0.1" in res["validated_nodes"]
        assert "127.0.0.2" in res["validated_nodes"]
        
        # Verify SFTP calls
        assert mock_sftp.open.call_count >= 6 # 3 test files * 2 nodes
        assert mock_sftp.remove.call_count >= 6 # Cleanup of 3 test files * 2 nodes

        # Verify ES calls via indices_repo
        service.indices_repo.exists_index_template.assert_called_once_with(name="dictionary_test_template")
        service.indices_repo.put_index_template.assert_called_once()
        service.indices_repo.create_index.assert_called_once_with(index_name="dictionary_test")
        service.indices_repo.analyze_text.assert_called_once()
        assert service.indices_repo.delete_index_safe.call_count >= 2 # Once before create, once in finally cleanup

    @pytest.mark.asyncio
    @patch("paramiko.SSHClient")
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.settings")
    async def test_publish_dictionaries_success(self, mock_settings, mock_ssh_class, mock_db, mock_es):
        """Test the whole publish process with SFTP backups, file writing, and DB updates"""
        mock_settings.SSH_DICTIONARY_DIR = "/etc/elasticsearch/analysis"
        mock_settings.GET_SSH_SERVERS = [
            {"host": "127.0.0.1", "port": 22, "username": "elastic", "key_path": "/path/to/id_rsa"},
            {"host": "127.0.0.2", "port": 22, "username": "elastic", "key_path": "/path/to/id_rsa"}
        ]

        service = DictionaryDeployService(mock_db, mock_es)

        # Set up mock repositories
        mock_data = {
            "user_dictionary": [
                {"word": "새로운단어", "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ],
            "decompound_dictionary": [],
            "synonym_dictionary": [],
            "correction_dictionary": [],
            "stopword_dictionary": []
        }
        self.setup_mock_repositories(service, mock_data)

        # Set up mock SSH and SFTP
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        
        # Simulate that old files exist on SFTP to test backup copy logic
        mock_sftp.stat.return_value = MagicMock()
        mock_sftp.open.return_value = MagicMock(read=MagicMock(return_value="기존내용"))
        
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh
        
        # Execute publishing
        res = await service.publish_dictionaries()

        assert res["status"] == "SUCCESS"
        assert res["nouns_count"] == 1
        
        # Verify backup directories were checked and files transferred
        assert mock_sftp.mkdir.call_count == 2 # 1 publish * 2 nodes = 2
        
        # Verify MongoDB update was called on the repository
        service.user_dict_repo.update_status.assert_called_once()
        call_args = service.user_dict_repo.update_status.call_args[1]
        assert call_args["key_value"] == "새로운단어"
        assert call_args["status"] == DictionaryStatus.APPLIED
        assert "applied_at" in call_args
        assert "applied_at_kst" in call_args

    @pytest.mark.asyncio
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.settings")
    async def test_validate_dictionaries_missing_key_path_failure(self, mock_settings, mock_db, mock_es):
        """Test that validation fails immediately if SSH_KEY_PATH is missing"""
        mock_settings.SSH_DICTIONARY_DIR = "/etc/elasticsearch/analysis"
        mock_settings.GET_SSH_SERVERS = [
            {"host": "127.0.0.1", "port": 22, "username": "elastic", "key_path": "", "password": ""}
        ]

        service = DictionaryDeployService(mock_db, mock_es)
        self.setup_mock_repositories(service, {})

        with pytest.raises(BizException) as excinfo:
            await service.validate_dictionaries()
        
        assert excinfo.value.status_code == 500
        assert "Neither SSH key_path nor password is provided" in excinfo.value.detail

    @pytest.mark.asyncio
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.settings")
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.paramiko.SSHClient")
    async def test_validate_dictionaries_generator_success(self, mock_ssh_class, mock_settings, mock_db, mock_es):
        """Test the validate async generator streaming progress steps"""
        mock_settings.SSH_DICTIONARY_DIR = "/etc/elasticsearch/analysis"
        mock_settings.GET_SSH_SERVERS = [
            {"host": "127.0.0.1", "port": 22, "username": "elastic", "key_path": "/path/to/key"},
            {"host": "127.0.0.2", "port": 22, "username": "elastic", "key_path": "/path/to/key"}
        ]

        mock_data = {
            "user_dictionary": [
                {"word": "새로운단어", "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ]
        }

        service = DictionaryDeployService(mock_db, mock_es)
        self.setup_mock_repositories(service, mock_data)

        # Set up mock SSH and SFTP
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        steps = []
        async for step in service.validate_dictionaries_generator():
            steps.append(step)

        # Ensure all validation progress steps are yielded
        assert len(steps) > 0
        step_types = [s["step"] for s in steps]
        assert "PREPROCESS" in step_types
        assert "SSH_CONNECT" in step_types
        assert "SFTP_UPLOAD" in step_types
        assert "ES_TEMPLATE" in step_types
        assert "ES_INDEX" in step_types
        assert "ES_ANALYZE" in step_types
        assert "CLEANUP" in step_types
        assert "COMPLETE" in step_types

        # Last step should be COMPLETE with SUCCESS
        assert steps[-1]["step"] == "COMPLETE"
        assert steps[-1]["status"] == "SUCCESS"

    @pytest.mark.asyncio
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.settings")
    @patch("src.python.elasticsearch.application.services.api.dictionary_deploy_service.paramiko.SSHClient")
    async def test_publish_dictionaries_generator_success(self, mock_ssh_class, mock_settings, mock_db, mock_es):
        """Test the publish async generator streaming progress steps"""
        mock_settings.SSH_DICTIONARY_DIR = "/etc/elasticsearch/analysis"
        mock_settings.GET_SSH_SERVERS = [
            {"host": "127.0.0.1", "port": 22, "username": "elastic", "key_path": "/path/to/key"},
            {"host": "127.0.0.2", "port": 22, "username": "elastic", "key_path": "/path/to/key"}
        ]

        mock_data = {
            "user_dictionary": [
                {"word": "새로운단어", "delete_yn": "N", "status": DictionaryStatus.APPROVED}
            ]
        }

        service = DictionaryDeployService(mock_db, mock_es)
        self.setup_mock_repositories(service, mock_data)

        # Set up mock SSH and SFTP
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_sftp.stat.return_value = MagicMock()
        mock_sftp.open.return_value = MagicMock(read=MagicMock(return_value="기존내용"))
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        steps = []
        async for step in service.publish_dictionaries_generator():
            steps.append(step)

        # Ensure all validation and publish progress steps are yielded
        assert len(steps) > 0
        step_types = [s["step"] for s in steps]
        assert "VALIDATE_START" in step_types
        assert "PREPROCESS" in step_types
        assert "SSH_BACKUP" in step_types
        assert "SFTP_DEPLOY" in step_types
        assert "DB_SYNC" in step_types
        assert "COMPLETE" in step_types

        # Last step should be COMPLETE with SUCCESS
        assert steps[-1]["step"] == "COMPLETE"
        assert steps[-1]["status"] == "SUCCESS"

