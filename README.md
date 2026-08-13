# gkeep

A command-line interface for Google Keep.


## Installation
Requires [`gkeepapi`](https://github.com/kiwiz/gkeepapi).
```sh
pip install gkeepapi
git clone https://github.com/notmattmoore/gkeep
chmod +x gkeep.py
```

## Configuration and Authentication

`gkeep.py` authenticates using a Google "master token", as supported by
`gkeepapi`. Login information is stored in the file `~/.config/gkeep.toml` or
`~/.binrc/gkeep.toml`, which is expected to have contents:
```toml
email = "example@gmail.com"
master_token = "aas_et/..."
cache_file = "..."  # optional
```
Obtaining a "master token" is (IMO) needlessly complicated, and using the
gkeepapi.login() method doesn't work at all. The master token is (reportedly)
equivalent to having the password to the account, but as opposed to allowing
users to manage their own passwords through app-specific passwords, the master
token flow seems designed to empower developers at the expense of users.

Obtaining the master token requires one to obtain an oauth token from their
Google account.
1. Open an Incognito Window in Google Chrome and open DevTools (F12).
1. Visit the Google Embedded Setup URL (accounts.google.com/EmbeddedSetup) and
   click through until "I Agree" (page might load forever after clicking).
1. Look at the DevTools Network tab, click through each request and look at
   cookies that contain the value "oauth_token" (there doesn't seem to be a good
   way to search aside from manually, the filter doesn't seem to work for cookie
   values).

NB: obviously, this might stop working based solely on the vicissitudes of
Google.

Once the oauth token has been obtained, use it to generate a master token.
1. Install [`gpsoauth`](https://github.com/simon-weber/gpsoauth).
1. Run the script below.
```python
import gpsoauth
res = gpsoauth.exchange_token("example@gmail.com", "oauth2_4/...", "0123456789abcdef")
print(res.get("Token"))
```
Use the oauth token obtained above as the second argument. The third argument is
an "Android ID", which can be any 16-digit hexadecimal string. `gpsoauth` is not
needed after the master token has been obtained.


## Usage
Below, `<note>` can be either the title of the note or the ID.

- `gkeep.py ls [--trashed] [--archived] [--case-sensitive] [pattern]`
   List notes. Accepts optional Python regular expression (ignores case by
   default, pass --case-sensitive to disable). If --trashed or --archived is
   passed, then also show trashed or archived notes, respectively.
- `gkeep.py find [--trashed] [--archived] [--case-sensitive] <pattern>`
   Search notes using a Python regular expression (ignores case by default, pass
   --case-sensitive to disable). If --trashed or --archived is passed, then also
   show trashed or archived notes, respectively.
- `gkeep.py new [--list] <note title>`
   Create a new note (option --list creates a list).
- `gkeep.py rm|delete <note>`
   Delete note.
- `gkeep.py archive|unarchive <note>`
   Toggle archive status of note.
- `gkeep.py pin|unpin <note>`
   Toggle pinned status of note.
-  `gkeep.py mv <note> <new_title>`
   Rename note.
-  `gkeep.py cp|copy <note> <new_title>`
   Copy note.
- `gkeep.py add <note> <item> [...]`
   Add checklist items (specified by sequence of strings) to note. A parent
   item may be specified with --parent <parent item>.
- `gkeep.py checkoff <note> <item> [...]`
   Check off checklist items (specified by sequence of strings) from note.
- `gkeep.py remove <note> <item> [...]`
   Remove (delete) checklist items (specified by sequence of strings) from
   note.
- `gkeep.py edit [--list] <note>`
   Edit note. If note doesn't exist, then create a new one (pass --list to
   create a new list).
- `gkeep.py cat|dump <note>`
   Print note contents to stdout.

#### Searching notes
```sh
gkeep.py ls "m[^aeiouy]"  # show notes with titles containing an 'm' followed by a consonant
gkeep.py find "todo"  # show notes with titles or bodies containing the text 'todo'
```

#### Create, delete, or archive a note
```sh
gkeep.py new "note one"  # text note
gkeep.py new --list  "note two"  # checklist note
gkeep.py edit "note three"  # creates a text note if it doesn't exist
gkeep.py edit --list "note three"  # creates a checklist note if it doesn't exist
gkeep.py rm "note one"
gkeep.py archive "note two"
```

#### Manipulate a checklist note
```sh
gkeep.py add "note one" "item one" "item two"  # add items
gkeep.py add "note one" "item three" --parent "parent item"  # add item under parent (parent is added if needed)
gkeep.py checkoff "note one" "item one" "item three"  # check off items
gkeep.py remove "note one" "item two" "parent item" # delete items
```

#### Editing
`edit` opens the note in `$EDITOR`. Text notes are edited directly, and
checklist notes are presented in a simple text format, an example of which is
given below.
```text
[ ] A
  [ ] B
  # some comment
  [ ] C
    # another comment
    [ ] E
    [ ] F
  [ ] D
[ ] G
[ ] unchecked
[X] checked
[c] also checked, any non-space character inside the brackets works
[ ] multi
    line item
# multi
# line comment
```
Multiline items and comments (lines beginning with whitespace followed by `#`)
are supported and preserved in the note. Saving the file updates the checklist
in Google Keep.
