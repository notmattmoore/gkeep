#!/usr/bin/python3
__description__ = "command-line interface to Google Keep"
__version__ = "2026-08-13"

CONFIG_FILE = "~/.binrc/gkeep.toml"
CONFIG_FILE_ALT = "~/.config/gkeep.toml"


# imports {{{1
import argparse
import os
import re
import subprocess as sp
import sys
import tempfile
import tomllib
from itertools import chain

import gkeepapi
from gkeepapi.node import List

try:  # mu fallback {{{
  import mylibs.utils as mu
except ImportError:
  import pickle
  class muFallback:
    @staticmethod
    def load(filepath):
      with open(filepath, "rb") as f:
        return pickle.load(f)
    @staticmethod
    def save(data, filepath):
      with open(filepath, "wb") as f:
        pickle.dump(data, f)
  mu = muFallback
#----------------------------------------------------------------------------}}}
#----------------------------------------------------------------------------}}}1


def error_and_exit(msg, exit_code=1): # {{{1
  """Print an error message and exit with exit code."""

  print(f"ERROR: {msg}", file=sys.stderr)
  raise SystemExit(exit_code)
#----------------------------------------------------------------------------}}}1

def notes_find(query, trashed=False): # {{{
  """Return array with all non-trashed notes with title $query or id $query. Pass
  trashed=True to include trashed notes as well."""

  if trashed:
    pred = lambda n: query in (n.title, n.id)
  else:
    pred = lambda n: not n.trashed and query in (n.title, n.id)
  return list(filter(pred, KEEP.all()))
#----------------------------------------------------------------------------}}}
def note_get(query, trashed=False):  # {{{
  """Return the note with title $query. If no such note exists, then interpret $query
  as the note id and return the associated note. If more than one note is to be
  returned, then issue a warning and return the first one."""

  notes = notes_find(query, trashed=trashed)
  if len(notes) == 0:
    error_and_exit(f"note '{query}' not found")
  if len(notes) > 1:
    print(f"WARNING: multiple notes '{query}' found, so using first one")
  return notes[0]
#---------------------------------------------------------------------------}}}

def note_info_str(note):  # {{{
  """Return the title of the note, a string showing the type (text, list) and status
  (pinned, trashed, archived), the ID of the note."""

  note_title = note.title if note.title != '' else "<untitled>"
  note_info = "list" if isinstance(note, List) else "text"

  if note.pinned:
    note_info += ", pinned"
  if note.archived:
    note_info += ", archived"
  if note.trashed:
    note_info += ", trashed"

  note_id = str(note.id)

  return (note_title, f"[{note_info}]", f"(ID: {note_id})")
#----------------------------------------------------------------------------}}}
def ls(r='', re_flags=re.IGNORECASE, trashed=False, archived=False):  # {{{
  """Print note titles. By default lists active (non-trashed, non-archived) notes."""

  r = re.compile(r, re_flags)

  # Find matching notes.
  notes_match = []
  for n in KEEP.all():
    if r.search(n.title) is not None:
      if not (n.trashed or n.archived): 
        notes_match.append(n)
      elif (n.trashed and trashed) or (n.archived and archived):
        notes_match.append(n)

  # Pull out the pinned notes to show first.
  notes_match_pinned = []
  notes_match_unpinned = []
  for n in notes_match:
    if n.pinned:
      notes_match_pinned.append(n)
    else:
      notes_match_unpinned.append(n)

  # Print notes with type, status, and ID. Align it all nicely.
  table = list(map(note_info_str, chain(notes_match_pinned, notes_match_unpinned)))
  widths = [max(len(str(item)) for item in col) for col in zip(*table)]
  for row in table:
    print(f"{row[0]:<{widths[0]}} {row[1]:<{widths[1]}} {row[2]:<{widths[2]}}")
#----------------------------------------------------------------------------}}}
def find(r, re_flags=re.IGNORECASE, trashed=False, archived=False): # {{{
  """Find notes matching regular expression r (case insensitive by default). Returns
  an array of dictionaries,
    [ {"note": n, "matches": [...]}, ... ],
  where matches is a non-empty array containing strings describing the matches."""

  r = re.compile(r, re_flags)

  results = []
  for n in KEEP.all():
    if n.trashed and not trashed:
      continue
    if n.archived and not archived:
      continue

    # store results in a dict containing the note and information about the matches.
    res = {"note": n, "matches": []}
    if r.search(n.title) is not None:
      res["matches"].append("(title)")
    if isinstance(n, List):
      n_text = format_list(n.items)
    else:
      n_text = n.text
    for (line_no, line) in enumerate(n_text.splitlines(), start=1):
      if r.search(line) is not None:
        res["matches"].append(f"(line {line_no}) {line}")
    if len(res["matches"]) > 0:
      results.append(res)

  return results
#----------------------------------------------------------------------------}}}
def find_print(r, re_flags=re.IGNORECASE, trashed=False, archived=False): # {{{
  """Find and print notes matching regular expression r (case insensitive by
  default)."""

  # Print notes with type, status, and ID and put match information in the line
  # after.
  for res in find(r, re_flags=re_flags, trashed=trashed, archived=archived):
    (n_title, n_status, n_id) = note_info_str(res["note"])
    m = '\n'.join(f"  {m}" for m in res["matches"])
    print(f"{n_title} {n_status} {n_id}\n{m}")
#----------------------------------------------------------------------------}}}

def new(title, make_list=False):  # {{{
  """Make a new note with the given title."""

  # make sure the title is unique
  if len(notes_find(title)) != 0:
    error_and_exit(f"note '{title}' already exists")

  if make_list:
    return KEEP.createList(title, [])
  else:
    return KEEP.createNote(title, "")
#----------------------------------------------------------------------------}}}
def rm(note_spec):  # {{{
  """Delete the note with the given title or ID."""

  note = note_get(note_spec)
  note.delete()
  return note
#----------------------------------------------------------------------------}}}
def archive(note_spec):  # {{{
  """Toggle archive status for the note with the given title or ID."""

  note = note_get(note_spec)
  note.archived = not note.archived
  return note
#----------------------------------------------------------------------------}}}
def pin(note_spec):  # {{{
  """Toggle pinned status for the note with the given title or ID."""

  note = note_get(note_spec)
  note.pinned = not note.pinned
  return note
#----------------------------------------------------------------------------}}}
def mv(note_spec, title_new): # {{{
  """Rename note. Make sure that the new title is unique."""

  note = note_get(note_spec)

  # make sure the new title is unique
  if len(notes_find(title_new)) != 0:
    error_and_exit(f"not renaming '{note.title}' since note '{title_new}' already exists")

  note.title = title_new
 
  return note
#----------------------------------------------------------------------------}}}

def require_list(note): # {{{
  """Check whether note is a List and error and exit if it is not."""

  if not isinstance(note, List):
    error_and_exit(f"note '{note.title}' is not a list")
#----------------------------------------------------------------------------}}}
def find_list_item(note, item, deleted=False, checked=False): # {{{
  """Return the list item with text $item. If deleted or checked, then also include
  deleted and checked items (respectively) in the search. If nothing is found, then
  return None."""

  for i in note.items:
    if i.text == item:
      if not (i.deleted or i.checked):
        return i
      elif (i.deleted and deleted) or (i.checked and checked):
        return i
  return None
#----------------------------------------------------------------------------}}}
def add(note_spec, item, parent=None): # {{{
  """Add $item to the list with title or ID $note_spec."""

  note = note_get(note_spec)
  require_list(note)

  # avoid duplicates
  if find_list_item(note, item) is not None:
    print(f"WARNING: note '{note_spec}' already has item named '{item}'")
    return note

  # Find the parent item if parent is specified. If the parent item doesn't exist,
  # then create it. Do this before adding the new list item to preserve sorting.
  if parent is not None:
    list_parent = find_list_item(note, parent)
    if list_parent is None:
      list_parent = note.add(parent)

  list_item = note.add(item)

  # Make the new item a child of the parent item (if specified).
  if parent is not None:
    list_parent.indent(list_item)

  return note
#----------------------------------------------------------------------------}}}
def remove(note_spec, item, delete=True): # {{{
  """Check off or delete $item from list with title or ID $note_spec."""

  note = note_get(note_spec)
  require_list(note)

  i = find_list_item(note, item, checked=True)
  if i is not None:
    if delete:
      i.delete()
    else:
      i.checked = True
    return note

  error_and_exit(f"'{item}' not found in list '{note.title}'")
#----------------------------------------------------------------------------}}}

def format_list(items, prefix='', seen=None): # {{{
  """Recursively format the array items (each element should have a element.subitems
  attribute, which is a list). An example of the formatting is given below.
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
    [ ] multi
        line item
    # multi
    # line comment
  Comments are supported in the form of a list item whose text begins with whitesace
  followed by '#'. Google Keep currently only supports rather dumb nesting of list
  items with the element.indented boolean, but this function allows for arbitrarily
  deep sublists."""

  if seen is None:
    seen = []

  checkbox = lambda i: "[ ]" if not i.checked else "[X]"
  item_format = lambda i: f"{prefix}{checkbox(i)} {i.text}\n"
  comment_format = lambda i: f"{prefix}{i.text.strip()}\n"
  indent = "  "

  r = ""
  for i in items:
    if i in seen or i.deleted:
      continue
    if re.search(r"^ *#", i.text) is None:
      r += item_format(i)
    else:  # item is a stored comment
      r += comment_format(i)
    seen.append(i)
    if len(i.subitems) > 0:
      r += format_list(i.subitems, prefix=prefix + indent, seen=seen) + "\n"

  return r.rstrip()
#----------------------------------------------------------------------------}}}
def note_str(note, do_format_list=True):  # {{{
  """Return the contents of a note as a string. If $do_format_list, then nicely
  format list items as described in format_list()."""

  if isinstance(note, List) and do_format_list:
    return format_list(note.items)
  else:
    return note.text
#----------------------------------------------------------------------------}}}
def _parse_list_recurse(item_lines, i=0, indent=0): # {{{
  """Recursion helper for parse_list(). Takes the list of item lines, the current
  index we are parsing at, and the indentation level. Returns the list of items as
  described in parse_list() and the index at which the current call stopped
  recursing."""

  items = []
  while i < len(item_lines):
    line = item_lines[i]

    # If line is less indented than the list we are parsing, then it must be an
    # outer-level list, so we are done parsing this current inner-level list and
    # should return.
    I = re.search(r"^ {" + str(indent) + ",}", line)
    if I is None:
      return (items, i)
    # If the line is equally indented, then add the item to the list of items.
    elif I.end() == indent:
      if (P := re.search(r"^ *\[.\] *", line)) is not None:  # checkbox
        item_text = line[P.end():]
      elif (P := re.search(r"^ *#", line)) is not None:  # comment
        item_text = "#" + line[P.end():]
      else:
        error_and_exit(f"unexpected item line encountered in _parse_list_recurse() {line=}.")
      items.append({
        "text"     : item_text,
        "children" : [],
        "checked"  : (re.search(r"^ *\[[^ ]\]", line) is not None)
      })
      i += 1
    # Otherwise, the line must be more indented than the current list and so
    # represents a sublist of the previous list item. In this case we recurse and use
    # the result as the children of the previous item. The children array must be
    # added to (not replaced) in order to handle inconsistent indentation.
    else:
      (c, i) = _parse_list_recurse(item_lines, i=i, indent=I.end())
      items[-1]["children"].extend(c)

  return (items, i)
#----------------------------------------------------------------------------}}}
def parse_list(items_formatted):  # {{{
  """Parse the string items_formatted (output from format_list()) to reconstruct the
  list. Returns an array of dictionaries of the form
    [{"text": <item text>, "children": [...], "checked": <bool>}, ...],
  where the "children" array is of the same format as the overall array. Comments are
  supported in the items_formatted string by having the line start with whitespace
  followed by a #. Multi-line entries are also supported."""

  # Concatenate multi-line items. If a line starts with a checkbox or comment, then
  # preserve it and whitespace (important for detecting sublists). If a line doesn't
  # start with a check box, then strip leading and trailing whitespace from it and
  # concatenate it with the previous line.
  item_lines = []
  for line in items_formatted.splitlines():
    if re.search(r"^ *\[.\]", line) is not None: # regular checkbox
      # leading whitespace is important for detecting sublist items, so keep it
      item_lines.append(line.rstrip())
    elif (M := re.search(r"^ *#", line)) is not None: # comment
      # If the previous line was a comment at the same indentation level, then this
      # comment and the previous should be joined in a single entry.
      if len(item_lines) > 0 and (prev_M := re.search(r"^ *#", item_lines[-1])) is not None:
        if M.end() == prev_M.end(): # equal comment indentation levels, so join lines
          item_lines[-1] += f" {line[M.end():].strip()}"
        else: # differing comment indentation levels
          item_lines.append(line.rstrip())
      else:
        item_lines.append(line.rstrip())
    elif len(item_lines) > 0:  # muli-line entry
      # Remove leading and trailing whitespace.
      item_lines[-1] += f" {line.strip()}"
    elif line.strip() == '':  # skip blank lines
      continue
    else:  # bad formatting...
      error_and_exit(f"list\n--\n{items_formatted}\n--\nis incorrectly formatted.")

  # recursively process the array of lines and return
  items, _ = _parse_list_recurse(item_lines)
  return items
#----------------------------------------------------------------------------}}}
def list_replace(note, items_new, recursed=False): # {{{
  """Replace the note's items with the new items. items_new is an array of the form
  described in parse_list(). Returns the modified note unless called recursively. If
  called recursively, then do not delete existing items and return an array of the
  list items."""

  if not recursed:
    # gkeepapi doesn't have a bulk delete...
    for i in list(note.items):
      i.delete()

  # Add the items to the note. If children are encountered, then recurse.
  list_items = []
  for item in items_new:
    list_items.append(
      note.add(item["text"], item["checked"], gkeepapi.node.NewListItemPlacementValue.Bottom)
    )
    if len(item["children"]) > 0:  # recurse
      for c in list_replace(note, item["children"], recursed=True):
        list_items[-1].indent(c)

  if not recursed:
    return note
  else:
    return list_items
#----------------------------------------------------------------------------}}}
def edit(note_spec, new_list=False):  # {{{
  """Edit the contents of a note (specified by title or ID). If the note is a list,
  then format it nicely and parse the edited version. If the note doesn't exist, then
  create it (make it a list if $new_list)."""

  if len(notes_find(note_spec)) == 0: # create a new note if one doesn't exist.
    note = new(note_spec, make_list=new_list)
  else:
    note = note_get(note_spec)
  note_contents = note_str(note)

  # Put the note contents in a temporary file.
  with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
    tmpfile = f.name
    f.write(note_contents)

  # Edit the file in $EDITOR and read back the possibly modified contents.
  try:
    sp.run([os.environ.get("EDITOR", "vim"), tmpfile], check=True)
    with open(tmpfile, mode='r') as f:
      note_contents_edited = f.read()
  except Exception as err:
    error_and_exit(f"failed to edit note '{note.title}':\n  {err}")
  finally:
    if os.path.exists(tmpfile):
      os.remove(tmpfile)

  # Return if the note has not been edited.
  if note_contents_edited == note_contents:
    return note

  # If the note was a list, then we need to replace all the items with the new items.
  if isinstance(note, List):
    note = list_replace(note, parse_list(note_contents_edited))
  else:
    note.text = note_contents_edited

  return note
#----------------------------------------------------------------------------}}}
def cat(note_spec, do_format_list=True):  # {{{
  """Print the contents of note (specified by title or ID) to stdout."""
 
  note = note_get(note_spec)
  print(note_str(note, do_format_list=do_format_list), file=sys.stdout)
  return note
#----------------------------------------------------------------------------}}}


if __name__ == "__main__":  # {{{1
  # argument parsing {{{
  parser = argparse.ArgumentParser(description=__description__)
  parser.add_argument("--version", "-v", action="version", version="%(prog)s " + __version__)
  sub = parser.add_subparsers(dest="command", required=True)

  # ls
  parser_ls = sub.add_parser(
    "ls",
    help="List notes. Accepts optional Python regular expression (ignores case by"
         " default, pass --case-sensitive to disable). If --trashed or --archived is"
         " passed, then also show trashed or archived notes, respectively."
  )
  parser_ls.add_argument(
    "--trashed", action="store_true", help="Also list trashed notes."
  )
  parser_ls.add_argument(
    "--archived", action="store_true", help="Also list archived notes."
  )
  parser_ls.add_argument("--case-sensitive", action="store_true")
  parser_ls.add_argument(
    "pattern", nargs='?', default='',
    help="Python regular expression (optional)."
  )

  # find
  parser_find = sub.add_parser(
    "find",
    help="Search notes using a Python regular expression (ignores case by default,"
         " pass --case-sensitive to disable). If --trashed or --archived is passed,"
         " then also show trashed or archived notes, respectively."
  )
  parser_find.add_argument(
    "--trashed",
    action="store_true", help="Also search trashed notes."
  )
  parser_find.add_argument(
    "--archived",
    action="store_true", help="Also search archived notes."
  )
  parser_find.add_argument("--case-sensitive", action="store_true")
  parser_find.add_argument("pattern", help="Python regular expression")

  # new
  parser_new = sub.add_parser(
    "new",
    help="Create a new note (option --list creates a list)."
  )
  parser_new.add_argument("--list", action="store_true")
  parser_new.add_argument("note_title", help="The title of the note to create.")

  # rm | delete
  parser_rm = sub.add_parser(
    "rm", aliases=["delete"], help="Delete note by title or ID."
  )
  parser_rm.add_argument(
    "note_spec", help="The title or ID of the note to delete."
  )
  parser_rm.set_defaults(command="rm")

  # archive | unarchive
  parser_archive = sub.add_parser(
    "archive", aliases=["unarchive"], help="Toggle archive status of note by title or ID."
  )
  parser_archive.add_argument(
    "note_spec", help="The title or ID of the note to archive/unarchive."
  )
  parser_archive.set_defaults(command="archive")

  # pin | unpin
  parser_pin = sub.add_parser(
    "pin", aliases=["unpin"], help="Toggle pinned status of note by title or ID."
  )
  parser_pin.add_argument(
    "note_spec", help="The title or ID of the note to pin/unpin."
  )
  parser_pin.set_defaults(command="pin")

  # mv | rename
  parser_mv = sub.add_parser(
    "mv", aliases=["rename"], help="Rename note by title or ID."
  )
  parser_mv.add_argument("note_spec", help="The title or ID of the note to rename.")
  parser_mv.add_argument("new_title", help="The new title of the note.")
  parser_mv.set_defaults(command="mv")

  # add
  parser_add = sub.add_parser(
    "add",
    help="Add checklist items (specified by sequence of strings) to note specified"
         " by title or ID. A parent item may be specified with --parent"
         " <parent item>."
  )
  parser_add.add_argument(
    "note_spec", help="The title or ID of the note to add items to."
  )
  parser_add.add_argument("items", nargs='+')
  parser_add.add_argument("--parent", help="set the parent of the item(s)")

  # checkoff
  parser_checkoff = sub.add_parser(
    "checkoff",
    help="Check off checklist items (specified by sequence of strings) from note"
         " specified by title or ID."
  )
  parser_checkoff.add_argument(
    "note_spec", help="The title or ID of the note to check items off from."
  )
  parser_checkoff.add_argument("items", nargs="+")

  # remove
  parser_remove = sub.add_parser(
    "remove",
    help="Remove (delete) checklist items (specified by sequence of strings) from"
         " note specified by title or ID."
  )
  parser_remove.add_argument(
    "note_spec", help="The title or ID of the note to remove items from."
  )
  parser_remove.add_argument("items", nargs="+")

  # edit
  parser_edit = sub.add_parser(
    "edit",
    help="Edit note. If note doesn't exist, then create a new one (pass --list to"
         " create a new list)."
  )
  parser_edit.add_argument("--list", action="store_true")
  parser_edit.add_argument("note_spec", help="The title or ID of the note to edit.")

  # cat | dump
  parser_cat = sub.add_parser(
    "cat", aliases=["dump"],
    help="Print note (specified by title or ID) contents to stdout."
  )
  parser_cat.set_defaults(command="cat")
  parser_cat.add_argument("note_spec", help="The title or ID of the note to cat.")
 
  args = parser.parse_args()
  #----------------------------------------------------------------------------}}}

  # Load configuration file
  CONFIG_FILE = os.path.expanduser(CONFIG_FILE)
  CONFIG_FILE_ALT = os.path.expanduser(CONFIG_FILE_ALT)
  if not os.path.exists(CONFIG_FILE):
    if not os.path.exists(CONFIG_FILE_ALT):
      error_and_exit(f"could not find configuration file {CONFIG_FILE} or {CONFIG_FILE_ALT}")
    else:
      CONFIG_FILE = CONFIG_FILE_ALT
  with open(CONFIG_FILE, "rb") as f:
    config = tomllib.load(f)
  if "email" not in config:
    error_and_exit(f"'email' field missing in {CONFIG_FILE}")
  if "master_token" not in config:
    error_and_exit(f"'master_token' field missing in {CONFIG_FILE}")
  config.setdefault("cache_file", "")
  config["cache_file"] = os.path.expanduser(config["cache_file"])

  # Authenticate
  KEEP = gkeepapi.Keep()
  try:
    if os.path.exists(config["cache_file"]):
      KEEP.authenticate(config["email"], config["master_token"], state=mu.load(config["cache_file"]))
    else:
      KEEP.authenticate(config["email"], config["master_token"])
  except Exception as err:
    error_and_exit(f"authentication failed:\n  {err}")

  # Run command
  if args.command == "ls":
    re_flags = 0 if args.case_sensitive else re.IGNORECASE
    ls(r=args.pattern, re_flags=re_flags, trashed=args.trashed, archived=args.archived)
  elif args.command == "find":
    re_flags = 0 if args.case_sensitive else re.IGNORECASE
    find_print(args.pattern, re_flags=re_flags, trashed=args.trashed, archived=args.archived)
  elif args.command == "new":
    new(args.note_title, make_list=args.list)
  elif args.command == "rm":
    rm(args.note_spec)
  elif args.command == "archive":
    archive(args.note_spec)
  elif args.command == "pin":
    pin(args.note_spec)
  elif args.command == "mv":
    mv(args.note_spec, args.new_title)
  elif args.command == "add":
    for i in args.items:
      add(args.note_spec, i, parent=args.parent)
  elif args.command == "checkoff":
    for i in args.items:
      remove(args.note_spec, i, delete=False)
  elif args.command == "remove":
    for i in args.items:
      remove(args.note_spec, i)
  elif args.command == "edit":
    edit(args.note_spec, new_list=args.list)
  elif args.command == "cat":
    cat(args.note_spec)
  else:
    error_and_exit(f"unhandled sequence of arguments encountered!\n  {args}")

  # Synchronize and cache the state
  try:
    KEEP.sync()
  except Exception as err:
    error_and_exit(f"sync failed:\n  {err}")
  if config["cache_file"] != "":
    if (dirname := os.path.dirname(config["cache_file"])) != "":
      os.makedirs(dirname, exist_ok=True)  # create the config directory if needed
    mu.save(KEEP.dump(), config["cache_file"])
#----------------------------------------------------------------------------}}}1
