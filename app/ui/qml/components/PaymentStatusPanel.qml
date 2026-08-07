import QtQuick
import SellMate 1.0

Column {
    id: root
    property string title: "Payment"
    property string message: ""
    spacing: Theme.gap
    width: parent ? parent.width : 400

    Text {
        width: parent.width
        text: root.title
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }

    Text {
        width: parent.width
        text: root.message.length > 0 ? root.message : "Follow the terminal prompts"
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        opacity: root.message.length > 0 ? 1 : 0.85
    }
}
