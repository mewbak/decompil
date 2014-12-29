from html import escape
from pygments.styles import get_style_by_name


DEFAULT_STYLE = get_style_by_name('native')


def format_to_str(obj):
    return ''.join(
        tok_text
        for tok_type, tok_text in obj.format()
    )


def tokens_to_dot(tokens, style=None):
    if not style:
        style = DEFAULT_STYLE

    result = []
    for tok_type, tok_text in tokens:
        tok_style = style.style_for_token(tok_type)
        markups_start = []
        markups_end = []

        def wrap_markup(tag, **attrs):
            markups_start.append('<{}{}>'.format(
                tag,
                ''.join(
                    ' {}="{}"'.format(key, value)
                    for key, value in attrs.items()
                )
            ))
            markups_end.append('</{}>'.format(tag))

        if tok_style['color']:
            wrap_markup('FONT', COLOR='#' + tok_style['color'])
        if tok_style['bold']:
            wrap_markup('B')
        result.append('{}{}{}'.format(
            ''.join(markups_start),
            '<BR ALIGN="left" />'.join(
                escape(chunk)
                for chunk in tok_text.split('\n')
            ),
            ''.join(reversed(markups_end))
        ))
    return '<{}>'.format(''.join(result))


def function_to_dot(func, style=None):
    if not style:
        style = DEFAULT_STYLE
    result = [
        'digraph {',
        'graph [{}];'.format(
            'bgcolor="{}"'.format(style.background_color)
            if style.background_color else
            ''
        )
    ]

    color_attr = (
        'color="{}"'.format(style.highlight_color)
        if style.highlight_color else
        ''
    )

    def bb_name(bb):
        return bb.name.lstrip('%')

    for bb in func:
        name = bb_name(bb)
        result.append('{} [shape=box,fontname=monospace,{},label={}];'.format(
            name, color_attr, tokens_to_dot(bb.format(), style),
        ))
        for succ in bb.get_successors(True):
            result.append('{} -> {};'.format(
                name, bb_name(succ)
            ))

    result.append('}')
    return '\n'.join(result)
