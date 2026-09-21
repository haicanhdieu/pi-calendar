"""Lazy inline Add Alert editor."""

_DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"

_START = (
    '<details open><summary>Add alert</summary><form method=POST action=/settings>'
    '<input name="alert_action" value=add type=hidden><label>Time '
    '<input name="alert_time" type=time required></label>'
    '<label><input name="alert_enabled" type=checkbox checked>Enabled</label>'
    '<fieldset><legend>Repeat on</legend>'
)
_END = '</fieldset><button>Save</button><button type=button disabled>Delete</button></form></details>'


def alert_editor_html():
    fields = []
    for index, name in enumerate(_DAYS.split("|")):
        fields.append('<label><input name=weekday_{} type=checkbox>{}</label>'.format(index, name))
    return _START + "".join(fields) + _END
