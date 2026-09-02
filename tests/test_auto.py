from scraperunner.fetcher.auto import looks_js_rendered

SHELL = """<html><body><div id="root"></div>
<a href="/">Home</a><a href="/login">Login</a><a href="/next">Next</a><a href="/x">X</a>
<script>window.data = [/* thousands of chars of JSON */ %s];</script>
</body></html>""" % ("1," * 2000)

CONTENT = "<html><body>" + "".join(
    f'<p>Paragraph number {i} with some readable text in it.</p><a href="/p/{i}">more</a>'
    for i in range(20)
) + "</body></html>"


def test_shell_page_with_big_script_is_detected():
    assert looks_js_rendered(SHELL)


def test_content_page_is_not_flagged():
    assert not looks_js_rendered(CONTENT)
