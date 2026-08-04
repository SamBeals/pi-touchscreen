import QtQuick

Column {
    property string message: "Something went wrong"
    spacing: Theme.gap
    width: parent ? parent.width - Theme.pageMargin * 2 : 400
    anchors.centerIn: parent

    Text {
        width: parent.width
        text: message
        color: Theme.error
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx - 4
        font.bold: true
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }
}
