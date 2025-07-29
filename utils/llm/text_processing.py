#!/usr/bin/env python3

import re

def convert_llm_output_to_readable(llm_output: str) -> str:
    """
    Converts an LLM output with markdown and formatting artifacts into clean, human-readable text.
    """
    if not llm_output:
        return ""

    text = llm_output.strip()
    # Split the text by <think> tags and take the part after the last <think> tag
    parts = text.split("<think>")
    if len(parts) > 1:
        # Take everything after the last <think> tag
        main_text = parts[-1].split("</think>")[-1].strip()
    else:
        # If no <think> tags are found, use the whole text
        main_text = text.strip()

    text = re.sub(r"\*\*(.*?)\*\*", r"\1", main_text)
    text = re.sub(r"- ", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s*:\s*", ": ", text)
    text = re.sub(r"#{1,6}\s+(.*?)(?:\n|$)", r"\1\n", text)

    paragraphs = text.split("\n\n")
    formatted_paragraphs = []
    for p in paragraphs:
        if p.strip():
            if "• " in p:
                formatted_paragraphs.append(p)
            else:
                formatted_p = re.sub(r"\s+", " ", p)
                formatted_paragraphs.append(formatted_p)

    clean_text = "\n\n".join(formatted_paragraphs)
    return clean_text
