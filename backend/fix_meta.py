with open(r'c:\Users\Windows\OneDrive\Desktop\aman\mini project\backend\static\script.js', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'Indian Road Accident Analytics \u00b7 2022\u20132024'
new = 'Kochi Road Accident Analytics \u00b7 2022\u20132026'
content2 = content.replace(old, new, 1)

if content2 != content:
    with open(r'c:\Users\Windows\OneDrive\Desktop\aman\mini project\backend\static\script.js', 'w', encoding='utf-8') as f:
        f.write(content2)
    print('SUCCESS: Updated PAGE_META dashboard sub')
else:
    print('ERROR: replacement not found')
