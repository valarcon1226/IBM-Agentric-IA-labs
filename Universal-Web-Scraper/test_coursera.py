from coursera import cml_to_md, safe


def test_cml_to_md():
    cml = ('<co-content><heading level="2">Tools</heading><text>Use <strong>tools</strong>.</text>'
           '<list bulletType="numbers"><li><text>one</text></li><li><text>two</text></li></list>'
           '<img assetId="abc"/><code language="python">print(1)</code></co-content>')
    md = cml_to_md(cml, lambda aid: f"assets/{aid}.png")
    assert "## Tools" in md
    assert "**tools**" in md
    assert "1. one" in md and "2. two" in md
    assert "\n\n![](assets/abc.png)\n\n" in md
    assert "print(1)" in md
    assert "assets" not in cml_to_md('<img assetId="x"/>')  # no resolver -> image dropped, no crash


def test_safe():
    assert safe('Lab: Build "X" / Y?') == "Lab Build X  Y"
    assert safe("...") == "sin-nombre"
