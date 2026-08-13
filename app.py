from consultant import ask_consultant


def main():
    question = input(
        "Ask a question about the FHWA MSAT documents: "
    ).strip()

    if not question:
        raise SystemExit("No question entered.")

    try:
        result = ask_consultant(question)
    except Exception as error:
        raise SystemExit(f"ERROR: {error}") from error

    print("\nOmni Consultant:")
    print(result["answer"])

    if result["sources"]:
        print("\nRetrieved source pages:")

        for source in result["sources"]:
            if source["page"] is not None:
                print(
                    f"- {source['filename']}, "
                    f"electronic PDF page {source['page']}"
                )
            else:
                print(f"- {source['filename']}")
    else:
        print(
            "\nWARNING: The response did not return any file citations."
        )


if __name__ == "__main__":
    main()