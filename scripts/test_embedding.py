from mcp_servers.rag_server.embedding_service import EmbeddingService


def main() -> None:
    embedding_service = EmbeddingService()

    test_passage = (
        "退貨率是退貨商品數除以銷售商品數，"
        "可用來衡量商品銷售後的退貨情況。"
    )

    test_query = "退貨率要怎麼計算？"

    passage_vectors = embedding_service.embed_passages(
        [test_passage]
    )

    query_vector = embedding_service.embed_query(
        test_query
    )

    print("模型名稱：")
    print(embedding_service.settings.rag_embedding_model)

    print("\n向量維度：")
    print(embedding_service.vector_size)

    print("\n文件向量數量：")
    print(len(passage_vectors))

    print("\n文件向量前五個數值：")
    print(passage_vectors[0][:5])

    print("\n查詢向量前五個數值：")
    print(query_vector[:5])


if __name__ == "__main__":
    main()