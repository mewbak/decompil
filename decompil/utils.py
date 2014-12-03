def format_to_str(obj):
    return ''.join(
        tok_text
        for tok_type, tok_text in obj.format()
    )
