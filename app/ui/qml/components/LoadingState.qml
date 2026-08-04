import QtQuick

Column {
    id: root
    property string message: "Loading…"
    spacing: Theme.sectionGap
    anchors.centerIn: parent
    width: parent ? parent.width - Theme.pageMargin * 2 : 400

    Text {
        width: parent.width
        text: root.message
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }
}
