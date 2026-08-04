import QtQuick
import SellMate 1.0

Column {
    id: root
    property string message: "Loading…"
    spacing: Theme.sectionGap
    anchors.centerIn: parent
    width: parent ? parent.width - Theme.pageMargin * 2 : 400

    Text {
        width: parent.width
        text: Theme.businessName
        color: Theme.primary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
    }

    Text {
        width: parent.width
        text: root.message
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }
}
