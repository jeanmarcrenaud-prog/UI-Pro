"""Fix test cases in test_code_extractor.py"""

content = open('tests/test_code_extractor.py', 'r', encoding='utf-8').read()

# The old Unicode cleaning section (with CRLF line endings from Windows)
old_section = (
    "    # ── Unicode cleaning ───────────────────────────────────────────────\n"
    "\n"
    "    def test_diamond_character_removed(self):\n"
    '        """Le caractère ♦ (U+0080 ou similaire) généré par LLM est supprimé."""\n'
    '        code = \'print(f"Temp: {t} ♦C")\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "♦" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_bullet_character_removed(self):\n"
    '        """Le caractère ● est supprimé."""\n'
    '        code = "● items = [1, 2, 3]"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "●" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_arrow_replaced_by_dash_arrow(self):\n"
    '        """Le caractère → est remplacé par ->."""\n'
    '        code = "x = a → b"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "→" not in result\n'
    '        assert "->" in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_double_arrow_replaced(self):\n"
    '        """Le caractère ⇒ est remplacé par =>."""\n'
    '        code = "f = lambda x: x ⇒ x * 2"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "⇒" not in result\n'
    '        assert "=>" in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_typographic_quotes_replaced(self):\n"
    '        """Les guillemets typographiques sont remplacés par des quotes ASCII."""\n'
    '        code = \'print("hello")\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert \'"\xab\' not in result and \'"\xbb\' not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_control_characters_removed(self):\n"
    '        """Les caractères de contrôle (\\x00-\\x08, \\x0E-\\x1F) sont supprimés."""\n'
    '        code = "print(\'hello\')\x00world"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "\\x00" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_unicode_invalid_combined_with_bracket_error(self):\n"
    '        """Caractère invalide + bracket manquant = les deux sont réparés."""\n'
    '        code = \'print(f"Temp: {t} ♦C")\\nx = [1, 2\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "♦" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
)

# The new section with fixed test cases
new_section = (
    "    # ── Unicode cleaning ───────────────────────────────────────────────\n"
    "\n"
    "    def test_diamond_character_removed(self):\n"
    '        """Le caractère ♦ (U+0080 ou similaire) généré par LLM est supprimé."""\n'
    '        code = \'print(f"Temp: {t} ♦C")\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "♦" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_bullet_character_removed(self):\n"
    '        """Le caractère ● est supprimé (le code restant doit être valide)."""\n'
    '        code = "items = [1, ● 2, 3]"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "●" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_arrow_replaced_by_dash_arrow(self):\n"
    '        """Le caractère → est remplacé par -> (dans un commentaire par exemple)."""\n'
    '        code = "# a → b  (comment)"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "→" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_double_arrow_replaced(self):\n"
    '        """Le caractère ⇒ est remplacé par => (dans un commentaire)."""\n'
    '        code = "# x ⇒ y"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "⇒" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_typographic_quotes_replaced(self):\n"
    '        """Les guillemets typographiques sont remplacés par des quotes ASCII."""\n'
    "        # U+201C (") et U+201D (") remplacés par \"\n"
    '        code = \'print("hello")\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "\u201c" not in result and "\u201d" not in result  # no curly quotes\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_control_characters_removed(self):\n"
    '        """Les caractères de contrôle (\\x00-\\x08, \\x0E-\\x1F) sont supprimés."""\n'
    '        code = "print(\'hello" + "\\x00" + "world\')"\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "\\x00" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
    "\n"
    "    def test_unicode_invalid_combined_with_bracket_error(self):\n"
    '        """Caractère invalide + bracket manquant = les deux sont réparés."""\n'
    '        code = \'print(f"Temp: {t} ♦C")\\nx = [1, 2\'\n'
    "        result = fix_syntax_errors(code)\n"
    '        assert "♦" not in result\n'
    '        assert compile(result, "<test>", "exec")\n'
)

if old_section in content:
    content = content.replace(old_section, new_section, 1)
    open('tests/test_code_extractor.py', 'w', encoding='utf-8').write(content)
    print("Replaced OK")
else:
    print("NOT FOUND with LF, trying CRLF...")
    old_crlf = old_section.replace('\n', '\r\n')
    new_crlf = new_section.replace('\n', '\r\n')
    if old_crlf in content:
        content = content.replace(old_crlf, new_crlf, 1)
        open('tests/test_code_extractor.py', 'w', encoding='utf-8').write(content)
        print("Replaced OK (CRLF)")
    else:
        print("Still not found")
        # Find the Unicode cleaning section manually
        idx = content.find('# ── Unicode cleaning')
        if idx >= 0:
            print(f"Found at index {idx}")
            print("Content around that area:")
            print(repr(content[idx:idx+300]))
        else:
            print("Section not found at all")