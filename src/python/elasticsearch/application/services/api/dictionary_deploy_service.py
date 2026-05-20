import logging
import paramiko
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from elasticsearch import AsyncElasticsearch
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.config.settings.env_settings import settings
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException
from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus
from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import get_now_utc, get_now_kst_str

# MongoDB Repositories
from src.python.elasticsearch.application.repository.mongodb.user_dictionary_repository import UserDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.decompound_dictionary_repository import DecompoundDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.synonym_dictionary_repository import SynonymDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.correction_dictionary_repository import CorrectionDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.stopword_dictionary_repository import StopwordDictionaryRepository

# Elasticsearch Repositories
from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import ElasticsearchCatRepository
from src.python.elasticsearch.application.repository.elasticsearch.indices_repository import ElasticsearchIndicesRepository

logger = logging.getLogger(__name__)

class DictionaryDeployService:
    def __init__(self, db: AsyncIOMotorDatabase, es_client: AsyncElasticsearch):
        # MongoDB Repositories
        self.user_dict_repo = UserDictionaryRepository(db)
        self.decompound_dict_repo = DecompoundDictionaryRepository(db)
        self.synonym_dict_repo = SynonymDictionaryRepository(db)
        self.correction_dict_repo = CorrectionDictionaryRepository(db)
        self.stopword_dict_repo = StopwordDictionaryRepository(db)
        
        # Elasticsearch Repositories
        self.cat_repo = ElasticsearchCatRepository(es_client)
        self.indices_repo = ElasticsearchIndicesRepository(es_client)

    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        """Helper to extract a field regardless of whether the object is a dict or a Pydantic model"""
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        if hasattr(obj, field_name):
            return getattr(obj, field_name)
        return default

    async def _get_all_dictionary_lines(self) -> Tuple[List[str], List[str], List[str], List[Dict[str, Any]]]:
        """
        Fetches active APPROVED and APPLIED documents across all 5 dictionary collections,
        formats them into lines, and returns:
        (noun_lines, synonym_lines, stop_lines, approved_docs_by_collection)
        """
        repos = {
            "user_dictionary": self.user_dict_repo,
            "decompound_dictionary": self.decompound_dict_repo,
            "synonym_dictionary": self.synonym_dict_repo,
            "correction_dictionary": self.correction_dict_repo,
            "stopword_dictionary": self.stopword_dict_repo
        }

        noun_lines = []
        synonym_lines = []
        stop_lines = []
        approved_docs_by_collection = []

        for col_name, repo in repos.items():
            # Query status via MongoDB repositories
            approved_docs = await repo.get_by_status(DictionaryStatus.APPROVED)
            applied_docs = await repo.get_by_status(DictionaryStatus.APPLIED)
            
            # Keep track of approved documents to update status later
            if approved_docs:
                approved_docs_by_collection.append({
                    "collection": col_name,
                    "docs": approved_docs
                })
            
            all_docs = approved_docs + applied_docs

            if col_name == "user_dictionary":
                for doc in all_docs:
                    word = self._get_field(doc, "word")
                    if word and str(word).strip():
                        noun_lines.append(str(word).strip())
            
            elif col_name == "decompound_dictionary":
                for doc in all_docs:
                    compound = self._get_field(doc, "compound_word")
                    components = self._get_field(doc, "components") or []
                    if compound and str(compound).strip() and components:
                        joined = " ".join(str(c).strip() for c in components if str(c).strip())
                        noun_lines.append(f"{str(compound).strip()} {joined}")
            
            elif col_name == "synonym_dictionary":
                for doc in all_docs:
                    synonyms = self._get_field(doc, "synonyms") or []
                    if synonyms:
                        joined = ",".join(str(s).strip() for s in synonyms if str(s).strip())
                        if joined:
                            synonym_lines.append(joined)
            
            elif col_name == "correction_dictionary":
                for doc in all_docs:
                    incorrect = self._get_field(doc, "incorrect")
                    corrected = self._get_field(doc, "corrected") or []
                    if incorrect and str(incorrect).strip() and corrected:
                        joined = ",".join(str(c).strip() for c in corrected if str(c).strip())
                        synonym_lines.append(f"{str(incorrect).strip()} => {joined}")
            
            elif col_name == "stopword_dictionary":
                for doc in all_docs:
                    word = self._get_field(doc, "word")
                    if word and str(word).strip():
                        stop_lines.append(str(word).strip())

        # Deduplicate and sort lines
        noun_lines = sorted(list(set(noun_lines)))
        synonym_lines = sorted(list(set(synonym_lines)))
        stop_lines = sorted(list(set(stop_lines)))

        return noun_lines, synonym_lines, stop_lines, approved_docs_by_collection

    def _get_ssh_client(self, server_conf: Any) -> paramiko.SSHClient:
        """Helper to create and return an SSH Client based on server configuration"""
        if isinstance(server_conf, str):
            server_conf = {
                "host": server_conf,
                "port": settings.SSH_PORT or 22,
                "username": settings.SSH_USERNAME,
                "password": settings.SSH_PASSWORD,
                "key_path": settings.SSH_KEY_PATH
            }
            
        ip = server_conf.get("host") or server_conf.get("ip")
        ssh_username = server_conf.get("username")
        ssh_port = server_conf.get("port") or 22
        ssh_password = server_conf.get("password")
        ssh_key_path = server_conf.get("key_path")

        if not ip:
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message="SSH host/ip is missing in server configuration"
            )

        if not ssh_username:
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"SSH username is missing for host {ip}"
            )

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if ssh_key_path:
                logger.info(f"Connecting to {ip}:{ssh_port} via SSH Key: {ssh_key_path}")
                ssh.connect(ip, port=ssh_port, username=ssh_username, key_filename=ssh_key_path, timeout=10)
            elif ssh_password:
                logger.info(f"Connecting to {ip}:{ssh_port} via SSH Password")
                ssh.connect(ip, port=ssh_port, username=ssh_username, password=ssh_password, timeout=10)
            else:
                raise BizException(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"Neither SSH key_path nor password is provided for host {ip}"
                )
            return ssh
        except Exception as e:
            logger.error(f"SSH Connection to {ip} failed: {e}")
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to connect to node {ip} via SSH/SFTP: {str(e)}"
            )

    def _transfer_file(self, sftp: paramiko.SFTPClient, filename: str, content: str):
        """Transfers a text file directly to the configured SSH directory"""
        remote_dir = settings.SSH_DICTIONARY_DIR
        if not remote_dir:
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message="SSH_DICTIONARY_DIR is not configured in environment settings"
            )
        
        remote_path = f"{remote_dir}/{filename}"
        try:
            with sftp.open(remote_path, "w") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to transfer file {filename} to {remote_path}: {e}")
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"SFTP file transfer to {remote_path} failed: {str(e)}"
            )

    async def validate_dictionaries(self) -> Dict[str, Any]:
        """
        Validates pending APPROVED dictionaries by transferring test files via SSH/SFTP,
        creating an ES index template and test index, analyzing sample words, and cleaning up.
        """
        # 1. Fetch servers via Settings
        servers = settings.GET_SSH_SERVERS
        if not servers:
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message="SSH servers are not configured in settings"
            )
        node_ips = [s.get("host") or s.get("ip") or "" for s in servers]
        
        # 2. Preprocess Dictionaries
        noun_lines, synonym_lines, stop_lines, approved_docs_list = await self._get_all_dictionary_lines()
        
        # Join lines with newlines
        noun_content = "\n".join(noun_lines) + "\n"
        synonym_content = "\n".join(synonym_lines) + "\n"
        stop_content = "\n".join(stop_lines) + "\n"

        logger.info(f"Loaded dictionaries. Nouns: {len(noun_lines)} lines, Synonyms: {len(synonym_lines)} lines, Stopwords: {len(stop_lines)} lines.")

        # Gather sample words to verify via analyze API
        sample_words = []
        for group in approved_docs_list:
            col_name = group["collection"]
            docs = group["docs"]
            if not docs:
                continue
            
            sample_doc = docs[0]
            if col_name == "user_dictionary":
                w = self._get_field(sample_doc, "word")
                if w: sample_words.append(str(w))
            elif col_name == "decompound_dictionary":
                w = self._get_field(sample_doc, "compound_word")
                if w: sample_words.append(str(w))
            elif col_name == "synonym_dictionary":
                syns = self._get_field(sample_doc, "synonyms") or []
                if syns: sample_words.append(str(syns[0]))
            elif col_name == "correction_dictionary":
                w = self._get_field(sample_doc, "incorrect")
                if w: sample_words.append(str(w))
            elif col_name == "stopword_dictionary":
                w = self._get_field(sample_doc, "word")
                if w: sample_words.append(str(w))

        # Default sample word if no approved records exist
        if not sample_words:
            sample_words.append("테스트")

        # 3. SFTP Upload Test Files (node_test.txt, synonym_test.txt, stop_test.txt)
        logger.info(f"Uploading validation files to nodes: {[s.get('host') for s in servers]}")
        for server in servers:
            ssh = self._get_ssh_client(server)
            try:
                sftp = ssh.open_sftp()
                try:
                    self._transfer_file(sftp, "noun_test.txt", noun_content)
                    self._transfer_file(sftp, "synonym_test.txt", synonym_content)
                    self._transfer_file(sftp, "stop_test.txt", stop_content)
                finally:
                    sftp.close()
            finally:
                ssh.close()

        # 4. Elasticsearch Test Index Template and Index Validation via Indices Repository
        template_name = "dictionary_test_template"
        index_name = "dictionary_test"
        
        try:
            # Check and create template if missing
            template_exists = await self.indices_repo.exists_index_template(name=template_name)
            if not template_exists:
                logger.info(f"Creating Elasticsearch index template: {template_name}")
                await self.indices_repo.put_index_template(
                    name=template_name,
                    index_patterns=["dictionary_test*"],
                    template={
                        "settings": {
                            "analysis": {
                                "tokenizer": {
                                    "test_nori_tokenizer": {
                                        "type": "nori_tokenizer",
                                        "decompound_mode": "mixed",
                                        "user_dictionary": "noun_test.txt"
                                    }
                                },
                                "filter": {
                                    "test_synonym_filter": {
                                        "type": "synonym",
                                        "synonyms_path": "synonym_test.txt"
                                    },
                                    "test_stopword_filter": {
                                        "type": "stop",
                                        "stopwords_path": "stop_test.txt"
                                    }
                                },
                                "analyzer": {
                                    "test_analyzer": {
                                        "type": "custom",
                                        "tokenizer": "test_nori_tokenizer",
                                        "filter": [
                                            "lowercase",
                                            "test_synonym_filter",
                                            "test_stopword_filter"
                                        ]
                                    }
                                }
                            }
                        },
                        "mappings": {
                            "properties": {
                                "text_field": {
                                    "type": "text",
                                    "analyzer": "test_analyzer"
                                }
                            }
                        }
                    }
                )

            # Recreate test index safely
            if await self.indices_repo.exists_index(index_name=index_name):
                await self.indices_repo.delete_index_safe(index_name=index_name)
            
            logger.info(f"Creating Elasticsearch test index: {index_name}")
            await self.indices_repo.create_index(index_name=index_name)

            # Sample analyze tests
            analyze_results = []
            for word in sample_words:
                try:
                    res = await self.indices_repo.analyze_text(
                        index_name=index_name,
                        analyzer="test_analyzer",
                        text=word
                    )
                    tokens = [token.get("token") for token in res.get("tokens", [])]
                    analyze_results.append({
                        "text": word,
                        "tokens": tokens
                    })
                except Exception as ex:
                    logger.error(f"Analyzer failed for word '{word}': {ex}")
                    raise BizException(
                        status_code=HTTP_400_BAD_REQUEST,
                        message=f"Analyzer failed to parse sample word '{word}': {str(ex)}"
                    )

            logger.info("Validation completed successfully.")
            return {
                "status": "SUCCESS",
                "validated_nodes": node_ips,
                "nouns_count": len(noun_lines),
                "synonyms_count": len(synonym_lines),
                "stopwords_count": len(stop_lines),
                "sample_analyzed": analyze_results
            }

        except Exception as e:
            if isinstance(e, BizException):
                raise e
            logger.error(f"Validation failed during ES operations: {e}")
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Validation failed during Elasticsearch operations: {str(e)}"
            )

        finally:
            # Clean up: delete test index safely
            try:
                await self.indices_repo.delete_index_safe(index_name=index_name)
            except Exception as e:
                logger.error(f"Failed to delete test index: {e}")

            # Clean up: delete test files from remote servers
            logger.info("Cleaning up validation test files from remote servers.")
            for server in servers:
                ssh = self._get_ssh_client(server)
                try:
                    sftp = ssh.open_sftp()
                    remote_dir = settings.SSH_DICTIONARY_DIR
                    for test_file in ["noun_test.txt", "synonym_test.txt", "stop_test.txt"]:
                        try:
                            sftp.remove(f"{remote_dir}/{test_file}")
                        except Exception:
                            pass
                    sftp.close()
                finally:
                    ssh.close()

    async def publish_dictionaries(self) -> Dict[str, Any]:
        """
        Publishes dictionaries to node servers after executing validation.
        Creates backup copies of existing files and updates approved MongoDB document statuses to APPLIED.
        """
        # 1. Run validation first to ensure everything is perfect
        logger.info("Triggering validation before publishing.")
        validation_res = await self.validate_dictionaries()
        if validation_res.get("status") != "SUCCESS":
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message="Pre-publish validation failed."
            )

        # 2. Preprocess Dictionaries
        servers = settings.GET_SSH_SERVERS
        if not servers:
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message="SSH servers are not configured in settings"
            )
        node_ips = [s.get("host") or s.get("ip") or "" for s in servers]
        noun_lines, synonym_lines, stop_lines, approved_docs_list = await self._get_all_dictionary_lines()
        
        # Join lines with newlines
        noun_content = "\n".join(noun_lines) + "\n"
        synonym_content = "\n".join(synonym_lines) + "\n"
        stop_content = "\n".join(stop_lines) + "\n"

        # KST Timestamp for backup (including seconds to handle quick consecutive clicks)
        kst_tz = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst_tz)
        timestamp = now_kst.strftime("%Y%m%d_%H%M%S")

        # 3. Publish to all node servers
        logger.info(f"Publishing dictionary files to nodes: {[s.get('host') for s in servers]}")
        for server in servers:
            ssh = self._get_ssh_client(server)
            ip = server.get("host") or server.get("ip")
            try:
                sftp = ssh.open_sftp()
                try:
                    remote_dir = settings.SSH_DICTIONARY_DIR
                    
                    # Ensure backup directory exists
                    backup_dir = f"{remote_dir}/backup"
                    try:
                        sftp.mkdir(backup_dir)
                    except OSError:
                        pass # Already exists
                    
                    # Back up existing files by reading their contents and writing to backup directory
                    files_to_backup = {
                        "noun.txt": f"noun_{timestamp}.txt",
                        "synonym.txt": f"synonym_{timestamp}.txt",
                        "stop.txt": f"stop_{timestamp}.txt"
                    }
                    
                    for original, backup_name in files_to_backup.items():
                        orig_path = f"{remote_dir}/{original}"
                        backup_path = f"{backup_dir}/{backup_name}"
                        try:
                            # Verify if file exists by stat-ing
                            sftp.stat(orig_path)
                            # Copy file content safely
                            with sftp.open(orig_path, "r") as r_orig:
                                content = r_orig.read()
                            with sftp.open(backup_path, "w") as w_backup:
                                w_backup.write(content)
                            logger.info(f"Created backup of {original} on node {ip} as {backup_name}")
                        except FileNotFoundError:
                            # File does not exist, nothing to back up
                            pass
                        except Exception as e:
                            logger.warning(f"Failed to back up {original} on node {ip}: {e}")

                    # Upload fresh full dictionary files
                    self._transfer_file(sftp, "noun.txt", noun_content)
                    self._transfer_file(sftp, "synonym.txt", synonym_content)
                    self._transfer_file(sftp, "stop.txt", stop_content)
                    logger.info(f"Uploaded fresh files to node {ip}")

                finally:
                    sftp.close()
            finally:
                ssh.close()

        # 4. Update MongoDB approved document statuses to APPLIED via repositories
        repos = {
            "user_dictionary": self.user_dict_repo,
            "decompound_dictionary": self.decompound_dict_repo,
            "synonym_dictionary": self.synonym_dict_repo,
            "correction_dictionary": self.correction_dict_repo,
            "stopword_dictionary": self.stopword_dict_repo
        }

        updated_counts = {}
        for group in approved_docs_list:
            col_name = group["collection"]
            docs = group["docs"]
            if not docs:
                continue
            
            repo = repos[col_name]
            
            # Determine correct key field for update matching
            key_field = "word"
            if col_name == "decompound_dictionary":
                key_field = "compound_word"
            elif col_name == "synonym_dictionary":
                key_field = "synonyms"
            elif col_name == "correction_dictionary":
                key_field = "incorrect"

            now_utc = get_now_utc()
            now_kst = get_now_kst_str()

            updated_count = 0
            for doc in docs:
                key_val = self._get_field(doc, key_field)
                if key_val:
                    # Update status via the Repository interface
                    success = await repo.update_status(
                        key_value=key_val,
                        status=DictionaryStatus.APPLIED,
                        applied_at=now_utc,
                        applied_at_kst=now_kst
                    )
                    if success:
                        updated_count += 1
            
            updated_counts[col_name] = updated_count
            logger.info(f"Updated status to APPLIED for {updated_count} documents in collection {col_name}")

        return {
            "status": "SUCCESS",
            "published_nodes": node_ips,
            "nouns_count": len(noun_lines),
            "synonyms_count": len(synonym_lines),
            "stopwords_count": len(stop_lines),
            "updated_documents": updated_counts
        }

    async def validate_dictionaries_generator(self):
        """
        Async generator version of validate_dictionaries to stream progress steps.
        """
        current_step = None
        step_display_names = {
            "PREPROCESS": "사전 데이터 정렬 및 중복 제거 가공",
            "SSH_CONNECT": "원격 사전 서버 SSH 연결",
            "SFTP_UPLOAD": "원격 서버에 검증용 테스트 사전 파일 전송",
            "ES_TEMPLATE": "엘라스틱서치 테스트용 인덱스 템플릿 생성",
            "ES_INDEX": "엘라스틱서치 테스트용 인덱스 재기동",
            "ES_ANALYZE": "형태소 분석 테스트 기동",
            "CLEANUP": "검증 자원 안전 회수 및 임시 파일 원격 삭제"
        }
        
        try:
            # Step 1: Preprocess Dictionaries
            current_step = "PREPROCESS"
            yield {"step": "PREPROCESS", "message": "사전 데이터 정렬 및 중복 제거 가공 중...", "status": "RUNNING"}
            servers = settings.GET_SSH_SERVERS
            if not servers:
                raise BizException(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    message="SSH 서버 정보가 환경 설정에 구성되지 않았습니다."
                )
                
            noun_lines, synonym_lines, stop_lines, approved_docs_list = await self._get_all_dictionary_lines()
            noun_content = "\n".join(noun_lines) + "\n"
            synonym_content = "\n".join(synonym_lines) + "\n"
            stop_content = "\n".join(stop_lines) + "\n"
            
            sample_words = []
            for group in approved_docs_list:
                col_name = group["collection"]
                docs = group["docs"]
                if not docs: continue
                sample_doc = docs[0]
                if col_name == "user_dictionary":
                    w = self._get_field(sample_doc, "word")
                    if w: sample_words.append(str(w))
                elif col_name == "decompound_dictionary":
                    w = self._get_field(sample_doc, "compound_word")
                    if w: sample_words.append(str(w))
                elif col_name == "synonym_dictionary":
                    syns = self._get_field(sample_doc, "synonyms") or []
                    if syns: sample_words.append(str(syns[0]))
                elif col_name == "correction_dictionary":
                    w = self._get_field(sample_doc, "incorrect")
                    if w: sample_words.append(str(w))
                elif col_name == "stopword_dictionary":
                    w = self._get_field(sample_doc, "word")
                    if w: sample_words.append(str(w))
                    
            if not sample_words:
                sample_words.append("테스트")
                
            yield {
                "step": "PREPROCESS", 
                "message": f"사전 데이터 가공 완료 (명사: {len(noun_lines)}행, 동의어: {len(synonym_lines)}행, 불용어: {len(stop_lines)}행)", 
                "status": "SUCCESS",
                "details": {
                    "nouns_count": len(noun_lines),
                    "synonyms_count": len(synonym_lines),
                    "stopwords_count": len(stop_lines)
                }
            }

            node_hosts_str = ", ".join([s.get("host") or s.get("ip") or "" for s in servers])

            # Step 2: SSH Connect
            current_step = "SSH_CONNECT"
            yield {"step": "SSH_CONNECT", "message": f"원격 사전 서버({node_hosts_str}) SSH 연결 시도 중...", "status": "RUNNING"}
            # Verify SSH connection for each node
            for server in servers:
                ssh = self._get_ssh_client(server)
                ssh.close()
            yield {"step": "SSH_CONNECT", "message": "모든 노드 서버 SSH 연결 성공", "status": "SUCCESS"}

            # Step 3: SFTP Upload
            current_step = "SFTP_UPLOAD"
            yield {"step": "SFTP_UPLOAD", "message": "원격 서버에 검증용 테스트 사전 파일 전송 중...", "status": "RUNNING"}
            for server in servers:
                ssh = self._get_ssh_client(server)
                try:
                    sftp = ssh.open_sftp()
                    try:
                        self._transfer_file(sftp, "noun_test.txt", noun_content)
                        self._transfer_file(sftp, "synonym_test.txt", synonym_content)
                        self._transfer_file(sftp, "stop_test.txt", stop_content)
                    finally:
                        sftp.close()
                finally:
                    ssh.close()
            yield {"step": "SFTP_UPLOAD", "message": "모든 노드 서버에 검증용 테스트 파일 전송 완료", "status": "SUCCESS"}

            # Step 4: ES Index Template
            current_step = "ES_TEMPLATE"
            yield {"step": "ES_TEMPLATE", "message": "엘라스틱서치 테스트용 인덱스 템플릿 생성 중...", "status": "RUNNING"}
            template_name = "dictionary_test_template"
            index_name = "dictionary_test"
            
            template_exists = await self.indices_repo.exists_index_template(name=template_name)
            if not template_exists:
                await self.indices_repo.put_index_template(
                    name=template_name,
                    index_patterns=["dictionary_test*"],
                    template={
                        "settings": {
                            "analysis": {
                                "tokenizer": {
                                    "test_nori_tokenizer": {
                                        "type": "nori_tokenizer",
                                        "decompound_mode": "mixed",
                                        "user_dictionary": "dictionary/noun_test.txt"
                                    }
                                },
                                "filter": {
                                    "test_pos_filter": {
                                        "stoptags": [
                                            "SC",
                                            "SE",
                                            "SF",
                                            "SP",
                                            "SSC",
                                            "SSO",
                                            "SY",
                                            "VCN",
                                            "VCP",
                                            "VSV",
                                            "VX"
                                        ],
                                        "type": "nori_part_of_speech"
                                    },
                                    "test_synonym_filter": {
                                        "type": "synonym",
                                        "synonyms_path": "dictionary/synonym_test.txt"
                                    },
                                    "test_stopword_filter": {
                                        "type": "stop",
                                        "stopwords_path": "dictionary/stop_test.txt"
                                    }
                                },
                                "analyzer": {
                                    "test_analyzer": {
                                        "type": "custom",
                                        "tokenizer": "test_nori_tokenizer",
                                        "filter": [
                                            "lowercase", 
                                            "test_pos_filter",
                                            "test_synonym_filter", 
                                            "test_stopword_filter",
                                            "remove_duplicates"
                                        ]
                                    }
                                }
                            }
                        },
                        "mappings": {
                            "properties": {
                                "text_field": {"type": "text", "analyzer": "test_analyzer"}
                            }
                        }
                    }
                )
            yield {"step": "ES_TEMPLATE", "message": "테스트 인덱스 템플릿 설정 완료", "status": "SUCCESS"}

            # Step 5: ES Index Create
            current_step = "ES_INDEX"
            yield {"step": "ES_INDEX", "message": "엘라스틱서치 테스트용 인덱스 재기동 중...", "status": "RUNNING"}
            if await self.indices_repo.exists_index(index_name=index_name):
                await self.indices_repo.delete_index_safe(index_name=index_name)
            await self.indices_repo.create_index(index_name=index_name)
            yield {"step": "ES_INDEX", "message": "테스트용 인덱스(dictionary_test) 활성화 완료", "status": "SUCCESS"}

            # Step 6: ES Analyze Test
            current_step = "ES_ANALYZE"
            yield {"step": "ES_ANALYZE", "message": f"형태소 분석 테스트 기동 중 (샘플 단어: {', '.join(sample_words)})...", "status": "RUNNING"}
            analyze_results = []
            for word in sample_words:
                try:
                    res = await self.indices_repo.analyze_text(
                        index_name=index_name,
                        analyzer="test_analyzer",
                        text=word
                    )
                    tokens = [token.get("token") for token in res.get("tokens", [])]
                    analyze_results.append({"text": word, "tokens": tokens})
                except Exception as ex:
                    raise BizException(
                        status_code=HTTP_400_BAD_REQUEST,
                        message=f"샘플 단어 '{word}'의 분석에 실패했습니다: {str(ex)}"
                    )
            yield {
                "step": "ES_ANALYZE", 
                "message": "형태소 분석기 테스트 분석 구동 성공", 
                "status": "SUCCESS",
                "details": {"sample_analyzed": analyze_results}
            }

            # Step 7: Clean up
            current_step = "CLEANUP"
            yield {"step": "CLEANUP", "message": "검증 자원 안전 회수 및 임시 파일 원격 삭제 중...", "status": "RUNNING"}
            try:
                await self.indices_repo.delete_index_safe(index_name=index_name)
            except Exception as e:
                logger.error(f"Failed to delete test index: {e}")
                
            for server in servers:
                ssh = self._get_ssh_client(server)
                try:
                    sftp = ssh.open_sftp()
                    remote_dir = settings.SSH_DICTIONARY_DIR
                    for test_file in ["noun_test.txt", "synonym_test.txt", "stop_test.txt"]:
                        try:
                            sftp.remove(f"{remote_dir}/{test_file}")
                        except Exception:
                            pass
                    sftp.close()
                finally:
                    ssh.close()
            yield {"step": "CLEANUP", "message": "임시 파일 및 모의 인덱스 삭제 완료", "status": "SUCCESS"}

            # Step 8: COMPLETE
            current_step = "COMPLETE"
            yield {
                "step": "COMPLETE", 
                "message": "축하합니다! 모든 검증 기준을 완벽하게 통과하여 즉시 배포할 수 있는 상태입니다.", 
                "status": "SUCCESS"
            }
        except Exception as e:
            logger.exception(f"Exception in validation generator step {current_step}")
            err_msg = str(e.detail) if hasattr(e, "detail") else str(e)
            if current_step:
                display_name = step_display_names.get(current_step, "진행")
                yield {
                    "step": current_step,
                    "message": f"{display_name} 실패: {err_msg}",
                    "status": "FAILED"
                }
            raise e

    async def publish_dictionaries_generator(self):
        """
        Async generator version of publish_dictionaries to stream progress steps.
        """
        current_step = None
        step_display_names = {
            "VALIDATE_START": "반영 전 선행 사전 검증 기동",
            "PREPROCESS": "반영 대상 데이터 로드 및 정렬 처리",
            "SSH_BACKUP": "기존 원격 서버 사전 파일 안전 백업",
            "SFTP_DEPLOY": "신규 정식 사전 파일 원격 서버 적용",
            "DB_SYNC": "데이터베이스 승인 상태(APPROVED -> APPLIED) 동기화",
        }
        try:
            # Step 1: Run Pre-publish Validation
            current_step = "VALIDATE_START"
            yield {"step": "VALIDATE_START", "message": "반영 전 선행 사전 검증 기동 중...", "status": "RUNNING"}
            async for val_step in self.validate_dictionaries_generator():
                if val_step["step"] == "COMPLETE" and val_step["status"] == "SUCCESS":
                    yield {"step": "VALIDATE_START", "message": "반영 전 선행 사전 검증 통과 완료", "status": "SUCCESS"}
                elif val_step["status"] == "FAILED":
                    yield {
                        "step": f"VAL_{val_step['step']}",
                        "message": f"[선행 검증] {val_step['message']}",
                        "status": "FAILED",
                        "details": val_step.get("details")
                    }
                    raise BizException(
                        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                        message="선행 유효성 검증 실패로 인해 배포가 중단되었습니다."
                    )
                else:
                    yield {
                        "step": f"VAL_{val_step['step']}",
                        "message": f"[선행 검증] {val_step['message']}",
                        "status": val_step["status"],
                        "details": val_step.get("details")
                    }

            # Step 2: Preprocess Dictionaries
            current_step = "PREPROCESS"
            yield {"step": "PREPROCESS", "message": "반영 대상 데이터 로드 및 정렬 처리 중...", "status": "RUNNING"}
            servers = settings.GET_SSH_SERVERS
            if not servers:
                raise BizException(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    message="SSH 서버 정보가 환경 설정에 구성되지 않았습니다."
                )
            noun_lines, synonym_lines, stop_lines, approved_docs_list = await self._get_all_dictionary_lines()
            noun_content = "\n".join(noun_lines) + "\n"
            synonym_content = "\n".join(synonym_lines) + "\n"
            stop_content = "\n".join(stop_lines) + "\n"
            
            now_utc = get_now_utc()
            now_kst = get_now_kst_str()
            
            # Format a timestamp for backup file naming (YYYYMMDD_HHMMSS including seconds)
            kst_tz = timezone(timedelta(hours=9))
            now_kst_dt = datetime.now(kst_tz)
            timestamp = now_kst_dt.strftime("%Y%m%d_%H%M%S")
            
            yield {"step": "PREPROCESS", "message": "배포 파일 데이터 가공 성공", "status": "SUCCESS"}

            # Step 3: SSH Backup
            current_step = "SSH_BACKUP"
            yield {"step": "SSH_BACKUP", "message": "기존 원격 서버 사전 파일 안전 백업 중...", "status": "RUNNING"}
            for server in servers:
                ssh = self._get_ssh_client(server)
                ip = server.get("host") or server.get("ip")
                try:
                    sftp = ssh.open_sftp()
                    try:
                        remote_dir = settings.SSH_DICTIONARY_DIR
                        backup_dir = f"{remote_dir}/backup"
                        try:
                            sftp.mkdir(backup_dir)
                        except OSError:
                            pass
                            
                        files_to_backup = {
                            "noun.txt": f"noun_{timestamp}.txt",
                            "synonym.txt": f"synonym_{timestamp}.txt",
                            "stop.txt": f"stop_{timestamp}.txt"
                        }
                        
                        for original, backup_name in files_to_backup.items():
                            orig_path = f"{remote_dir}/{original}"
                            backup_path = f"{backup_dir}/{backup_name}"
                            try:
                                sftp.stat(orig_path)
                                with sftp.open(orig_path, "r") as r_orig:
                                    content = r_orig.read()
                                with sftp.open(backup_path, "w") as w_backup:
                                    w_backup.write(content)
                            except FileNotFoundError:
                                pass
                    finally:
                        sftp.close()
                finally:
                    ssh.close()
            yield {"step": "SSH_BACKUP", "message": f"모든 대상 서버 노드에 사전 백업본 생성 완료 (backup/*_{timestamp}.txt)", "status": "SUCCESS"}

            # Step 4: SFTP Deploy
            current_step = "SFTP_DEPLOY"
            yield {"step": "SFTP_DEPLOY", "message": "신규 정식 사전 파일 원격 서버 적용 중...", "status": "RUNNING"}
            for server in servers:
                ssh = self._get_ssh_client(server)
                ip = server.get("host") or server.get("ip")
                try:
                    sftp = ssh.open_sftp()
                    try:
                        self._transfer_file(sftp, "noun.txt", noun_content)
                        self._transfer_file(sftp, "synonym.txt", synonym_content)
                        self._transfer_file(sftp, "stop.txt", stop_content)
                    finally:
                        sftp.close()
                finally:
                    ssh.close()
            yield {"step": "SFTP_DEPLOY", "message": "모든 노드 서버에 신규 정식 사전 파일 교체 완료", "status": "SUCCESS"}

            # Step 5: DB Sync
            current_step = "DB_SYNC"
            yield {"step": "DB_SYNC", "message": "데이터베이스 승인 상태(APPROVED -> APPLIED) 동기화 중...", "status": "RUNNING"}
            repos = {
                "user_dictionary": self.user_dict_repo,
                "decompound_dictionary": self.decompound_dict_repo,
                "synonym_dictionary": self.synonym_dict_repo,
                "correction_dictionary": self.correction_dict_repo,
                "stopword_dictionary": self.stopword_dict_repo
            }
            
            updated_counts = {}
            for group in approved_docs_list:
                col_name = group["collection"]
                docs = group["docs"]
                if not docs:
                    continue
                repo = repos[col_name]
                count = 0
                for doc in docs:
                    key_field = "word"
                    if col_name == "decompound_dictionary":
                        key_field = "compound_word"
                    elif col_name == "synonym_dictionary":
                        key_field = "synonyms"
                    elif col_name == "correction_dictionary":
                        key_field = "incorrect"
                    
                    val = self._get_field(doc, key_field)
                    if val:
                        await repo.update_status(
                            key_value=val,
                            status=DictionaryStatus.APPLIED,
                            applied_at=now_utc,
                            applied_at_kst=now_kst
                        )
                        count += 1
                updated_counts[col_name] = count
                
            yield {
                "step": "DB_SYNC", 
                "message": "데이터베이스 상태 최종 적용 동기화 완료", 
                "status": "SUCCESS",
                "details": updated_counts
            }

            # Step 6: COMPLETE
            current_step = "COMPLETE"
            yield {
                "step": "COMPLETE", 
                "message": "배포 완료! 사전 데이터가 원격 노드에 안전하게 반영되었으며 활성화되었습니다.", 
                "status": "SUCCESS"
            }
        except Exception as e:
            logger.exception(f"Exception in publish generator step {current_step}")
            err_msg = str(e.detail) if hasattr(e, "detail") else str(e)
            if current_step:
                display_name = step_display_names.get(current_step, "진행")
                yield {
                    "step": current_step,
                    "message": f"{display_name} 실패: {err_msg}",
                    "status": "FAILED"
                }
            raise e
