import QtQuick

Rectangle {
    property string name: ""
    property int quantity: 1
    property string lineTotalText: ""

    radius: Theme.cornerRadius
    color: Theme.surface
    implicitHeight: label.implicitHeight + 28
    width: parent ? parent.width : 400

    Text {
        id: label
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 14
        text: name + " × " + quantity + " — " + lineTotalText
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
    }
}
