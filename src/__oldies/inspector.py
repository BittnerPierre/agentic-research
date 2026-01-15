"""Outil d'inspection et téléchargement du contenu des vector stores OpenAI."""

import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import get_config
from ..vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class VectorStoreInspector:
    """Inspecte et télécharge le contenu d'un vector store OpenAI."""
    
    def __init__(self, client: OpenAI | None = None):
        self.config = get_config()
        self.client = client or OpenAI()
        
    def list_vector_store_files(self, vector_store_id: str) -> list[dict[str, Any]]:
        """
        Liste tous les fichiers attachés à un vector store.
        
        Args:
            vector_store_id: ID du vector store
            
        Returns:
            Liste des métadonnées de fichiers
        """
        try:
            logger.info(f"Listing files in vector store: {vector_store_id}")
            
            response = self.client.vector_stores.files.list(
                vector_store_id=vector_store_id,
                limit=100  # Ajustez selon vos besoins
            )
            
            files_info = []
            for file_obj in response.data:
                file_info = {
                    'id': file_obj.id,
                    'object': file_obj.object,
                    'created_at': file_obj.created_at,
                    'vector_store_id': file_obj.vector_store_id,
                    'status': file_obj.status,
                    'last_error': getattr(file_obj, 'last_error', None)
                }
                files_info.append(file_info)
            
            logger.info(f"Found {len(files_info)} files in vector store")
            return files_info
            
        except Exception as e:
            logger.error(f"Error listing vector store files: {e}")
            return []
    
    def retrieve_file_content(self, file_id: str) -> str | None:
        """
        Récupère le contenu d'un fichier par son ID.
        
        Args:
            file_id: ID du fichier OpenAI
            
        Returns:
            Contenu du fichier ou None en cas d'erreur
        """
        try:
            logger.info(f"Retrieving content for file: {file_id}")
            
            # Récupérer le contenu du fichier
            content = self.client.files.content(file_id)
            
            # Le contenu est retourné en bytes, le décoder en string
            return content.read().decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error retrieving file content for {file_id}: {e}")
            return None
    
    def get_file_metadata(self, file_id: str) -> dict[str, Any] | None:
        """
        Récupère les métadonnées d'un fichier.
        
        Args:
            file_id: ID du fichier OpenAI
            
        Returns:
            Métadonnées du fichier
        """
        try:
            file_obj = self.client.files.retrieve(file_id)
            return {
                'id': file_obj.id,
                'filename': file_obj.filename,
                'bytes': file_obj.bytes,
                'created_at': file_obj.created_at,
                'purpose': file_obj.purpose,
                'status': file_obj.status
            }
        except Exception as e:
            logger.error(f"Error retrieving file metadata for {file_id}: {e}")
            return None
    
    def download_vector_store_content(self, output_dir: str | None = None) -> dict[str, Any]:
        """
        Télécharge tout le contenu d'un vector store dans un dossier local.
        
        Args:
            output_dir: Dossier de sortie (optionnel, utilise la config par défaut)
            
        Returns:
            Rapport du téléchargement avec statistiques
        """
        # Obtenir l'ID du vector store
        manager = VectorStoreManager(self.client)
        vector_store_id = manager.get_or_create_vector_store()
        
        # Préparer le dossier de sortie
        if output_dir is None:
            output_dir = self.config.debug.output_dir
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Downloading vector store content to: {output_path}")
        
        # Statistiques du téléchargement
        download_stats = {
            'vector_store_id': vector_store_id,
            'output_directory': str(output_path),
            'files_found': 0,
            'files_downloaded': 0,
            'files_failed': 0,
            'total_bytes': 0,
            'files': []
        }
        
        # Lister les fichiers du vector store
        files_list = self.list_vector_store_files(vector_store_id)
        download_stats['files_found'] = len(files_list)
        
        if not files_list:
            logger.warning("No files found in vector store")
            return download_stats
        
        # Télécharger chaque fichier
        for file_info in files_list:
            file_id = file_info['id']
            
            try:
                # Récupérer les métadonnées pour avoir le nom du fichier
                metadata = self.get_file_metadata(file_id)
                if not metadata:
                    logger.error(f"Could not get metadata for file {file_id}")
                    download_stats['files_failed'] += 1
                    continue
                
                filename = metadata.get('filename', f"file_{file_id}.txt")
                file_bytes = metadata.get('bytes', 0)
                
                # Récupérer le contenu
                content = self.retrieve_file_content(file_id)
                if content is None:
                    logger.error(f"Could not retrieve content for file {file_id}")
                    download_stats['files_failed'] += 1
                    continue
                
                # Sauvegarder le fichier
                safe_filename = self._make_safe_filename(filename)
                file_path = output_path / f"{file_id}_{safe_filename}"
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Créer un fichier de métadonnées associé
                metadata_path = output_path / f"{file_id}_{safe_filename}.metadata.json"
                import json
                import time
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'file_info': file_info,
                        'metadata': metadata,
                        'downloaded_at': time.time(),
                        'local_path': str(file_path)
                    }, f, indent=2)
                
                download_stats['files_downloaded'] += 1
                download_stats['total_bytes'] += file_bytes
                download_stats['files'].append({
                    'id': file_id,
                    'filename': filename,
                    'local_path': str(file_path),
                    'bytes': file_bytes,
                    'status': 'success'
                })
                
                logger.info(f"Downloaded: {filename} -> {file_path}")
                
            except Exception as e:
                logger.error(f"Error downloading file {file_id}: {e}")
                download_stats['files_failed'] += 1
                download_stats['files'].append({
                    'id': file_id,
                    'filename': 'unknown',
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Créer un rapport de synthèse
        report_path = output_path / "download_report.json"
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(download_stats, f, indent=2)
        
        return download_stats
    
    def _make_safe_filename(self, filename: str) -> str:
        """Convertit un nom de fichier en nom sûr pour le système de fichiers."""
        import re
        # Remplacer les caractères problématiques
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limiter la longueur
        if len(safe_name) > 100:
            name, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
            safe_name = name[:95] + '.' + ext if ext else name[:100]
        return safe_name


def main():
    """Fonction principale pour télécharger le contenu du vector store."""
    
    inspector = VectorStoreInspector()
    
    print("🔍 Inspection du vector store...")
    
    try:
        # Télécharger tout le contenu
        stats = inspector.download_vector_store_content()
        
        print("\n📊 Rapport de téléchargement :")
        print(f"Vector Store ID: {stats['vector_store_id']}")
        print(f"Dossier de sortie: {stats['output_directory']}")
        print(f"Fichiers trouvés: {stats['files_found']}")
        print(f"Fichiers téléchargés: {stats['files_downloaded']}")
        print(f"Échecs: {stats['files_failed']}")
        print(f"Total téléchargé: {stats['total_bytes']} bytes")
        
        if stats['files_downloaded'] > 0:
            print("\n📁 Fichiers téléchargés :")
            for file_info in stats['files']:
                if file_info.get('status') == 'success':
                    print(f"  ✅ {file_info['filename']} ({file_info['bytes']} bytes)")
                    print(f"     -> {file_info['local_path']}")
        
        if stats['files_failed'] > 0:
            print("\n❌ Échecs :")
            for file_info in stats['files']:
                if file_info.get('status') == 'failed':
                    print(f"  ❌ {file_info.get('filename', 'unknown')}: {file_info.get('error', 'unknown error')}")
        
        print(f"\n📋 Rapport complet sauvegardé dans: {stats['output_directory']}/download_report.json")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'inspection: {e}")
        logger.error(f"Inspection failed: {e}")


if __name__ == "__main__":
    main() 