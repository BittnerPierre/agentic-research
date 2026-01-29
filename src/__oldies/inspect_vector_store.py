#!/usr/bin/env python3
"""Script pour inspecter et télécharger le contenu d'un vector store."""

import argparse
import sys

from .dataprep.inspector import VectorStoreInspector


def main():
    """Fonction principale avec arguments en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Inspect and download vector store content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python inspect_vector_store.py                    # Download to default dir
  python inspect_vector_store.py -o my_debug_dir    # Custom output directory
  python inspect_vector_store.py --list-only        # List files only, no download
        """,
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        help="Output directory for downloaded files (default: from config)",
    )

    parser.add_argument(
        "--list-only", action="store_true", help="Only list files, don't download content"
    )

    args = parser.parse_args()

    inspector = VectorStoreInspector()

    if args.list_only:
        # Mode listing seulement
        print("🔍 Listing vector store files...")

        # Obtenir l'ID du vector store
        from openai import OpenAI
        from vector_store_manager import VectorStoreManager

        client = OpenAI()
        manager = VectorStoreManager(client)
        vector_store_id = manager.get_or_create_vector_store()

        files_list = inspector.list_vector_store_files(vector_store_id)

        if not files_list:
            print("❌ No files found in vector store")
            return

        print(f"\n📁 Found {len(files_list)} files in vector store {vector_store_id}:")

        for i, file_info in enumerate(files_list, 1):
            # Récupérer les métadonnées pour avoir plus d'infos
            metadata = inspector.get_file_metadata(file_info["id"])

            print(f"\n{i}. File ID: {file_info['id']}")
            print(f"   Status: {file_info['status']}")
            print(f"   Created: {file_info['created_at']}")

            if metadata:
                print(f"   Filename: {metadata.get('filename', 'N/A')}")
                print(f"   Size: {metadata.get('bytes', 0)} bytes")
                print(f"   Purpose: {metadata.get('purpose', 'N/A')}")

            if file_info.get("last_error"):
                print(f"   ⚠️  Last Error: {file_info['last_error']}")

    else:
        # Mode téléchargement complet
        print("🔍 Inspecting and downloading vector store content...")

        try:
            stats = inspector.download_vector_store_content(args.output_dir)

            print("\n📊 Download Report:")
            print(f"Vector Store ID: {stats['vector_store_id']}")
            print(f"Output Directory: {stats['output_directory']}")
            print(f"Files Found: {stats['files_found']}")
            print(f"Files Downloaded: {stats['files_downloaded']}")
            print(f"Failures: {stats['files_failed']}")
            print(f"Total Downloaded: {stats['total_bytes']} bytes")

            if stats["files_downloaded"] > 0:
                print("\n📁 Downloaded Files:")
                for file_info in stats["files"]:
                    if file_info.get("status") == "success":
                        print(f"  ✅ {file_info['filename']} ({file_info['bytes']} bytes)")
                        print(f"     -> {file_info['local_path']}")

            if stats["files_failed"] > 0:
                print("\n❌ Failed Downloads:")
                for file_info in stats["files"]:
                    if file_info.get("status") == "failed":
                        print(
                            f"  ❌ {file_info.get('filename', 'unknown')}: {file_info.get('error', 'unknown error')}"
                        )

            print(f"\n📋 Full report saved to: {stats['output_directory']}/download_report.json")
            print(
                "\n💡 Tip: You can now inspect the downloaded .md files to see what's in your vector store!"
            )

        except Exception as e:
            print(f"❌ Error during inspection: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
