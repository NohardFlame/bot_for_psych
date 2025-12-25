# Telegram Message Formatting Guide

This guide explains how to use HTML formatting and emojis in your `.txt` files for Telegram messages.

## HTML Formatting

All text messages from `.txt` files now support HTML formatting. Simply use HTML tags in your text files:

### Available HTML Tags

- **Bold**: `<b>bold text</b>` or `<strong>bold text</strong>`
- **Italic**: `<i>italic text</i>` or `<em>italic text</em>`
- **Underline**: `<u>underlined text</u>`
- **Strikethrough**: `<s>strikethrough text</s>` or `<del>strikethrough text</del>`
- **Spoiler (hidden text)**: `<span class="tg-spoiler">spoiler text</span>`
- **Inline Code**: `<code>inline code</code>`
- **Preformatted Code Block**: `<pre>code block</pre>`
- **Hyperlink**: `<a href="https://example.com">link text</a>`

### Example

```
<b>День 1: Начало программы</b>

<i>Сегодня мы начнем с изучения основных концепций.</i>

Для дополнительной информации посетите: <a href="https://example.com">наш сайт</a>

<span class="tg-spoiler">Скрытый текст - нажмите, чтобы раскрыть</span>

<code>some_code_here()</code>
```

## Emojis

Emojis work directly in your `.txt` files - just copy and paste emoji characters:

- ✅ Check mark
- ❌ Cross mark
- 📅 Calendar
- 📁 Folder
- ⏳ Hourglass
- 📎 Paperclip
- 🔗 Link
- ⚠️ Warning
- 🎉 Celebration
- 🚀 Rocket
- ... and any other Unicode emoji

### Example with Emojis and HTML

```
<b>🎉 Добро пожаловать!</b>

<i>Сегодня мы начинаем новую программу! 🚀</i>

📅 День: 1
📁 Материалы готовы
✅ Все проверено

Посетите наш <a href="https://example.com">сайт</a> для дополнительной информации.
```

## Important Notes

1. **File Encoding**: Make sure your `.txt` files are saved with UTF-8 encoding to preserve emojis and special characters.

2. **HTML Escaping**: If you need to use literal `<` or `>` characters in your text (not as HTML tags), you can use:
   - `&lt;` for `<`
   - `&gt;` for `>`
   - `&amp;` for `&`

3. **Nested Tags**: You can nest HTML tags:
   ```
   <b>Bold text with <i>bold and italic</i> inside</b>
   ```

4. **Links**: Links must start with `http://` or `https://` to work properly.

5. **Mixed Content**: You can freely mix HTML formatting with emojis:
   ```
   <b>Важное сообщение!</b> ✅ <i>Не забудьте прочитать</i> 📖
   ```

## Where Formatting Works

HTML formatting is now enabled for:
- Text content from day folders (`.txt` files in day folders)
- Navigation messages (`msg.txt` files in present folder structure)
- All user-facing messages

Enjoy creating rich, formatted messages! 🎨

