import chromadb
from pathlib import Path

db_path = "backend/chroma_db" if Path("backend/chroma_db").exists() else "chroma_db"
client = chromadb.PersistentClient(path=db_path)

collection = client.get_collection("medical_guidelines")

print("Total vectors:", collection.count())

result = collection.get(
    limit=5,
    include=["documents", "metadatas", "embeddings"]
)

for i in range(len(result["ids"])):
    print("\n" + "=" * 60)
    print("ID:", result["ids"][i])
    print("Metadata:", result["metadatas"][i])

    embedding = result["embeddings"][i]

    print("Embedding dimensions:", len(embedding))
    print("First 10 values:", embedding[:10])

    print("Document:")
    print(result["documents"][i][:500])