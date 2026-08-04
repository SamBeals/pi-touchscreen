import QtQuick
import SellMate 1.0

Column {
    property string message: "Nothing here yet"
    spacing: Theme.gap
    width: parent ? Math.min(parent.width, 420) : 400

    Text {
        width: parent.width
        text: message
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }
}
