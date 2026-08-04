import QtQuick
import QtQuick.Controls

Button {
    id: root
    property bool danger: false
    property bool success: false
    property bool secondary: false

    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodyFontPx
    font.bold: true
    implicitHeight: Math.max(Theme.primaryButtonMinHeight, implicitContentHeight + 24)
    leftPadding: 28
    rightPadding: 28
    topPadding: 16
    bottomPadding: 16

    background: Rectangle {
        radius: Theme.buttonShape === "pill" ? height / 2
              : Theme.buttonShape === "square" ? 4
              : Theme.cornerRadius
        color: {
            if (!root.enabled) return Theme.secondary
            if (root.down) return Qt.darker(_fill(), 1.15)
            return _fill()
        }
        border.width: Theme.buttonStyle === "outline" ? 2 : 0
        border.color: root.danger ? Theme.error : Theme.primary
        opacity: Theme.buttonStyle === "soft" ? 0.9 : 1
    }

    contentItem: Text {
        text: root.text
        font: root.font
        color: Theme.buttonStyle === "outline" ? (root.danger ? Theme.error : Theme.primary) : "#FFFFFF"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }

    function _fill() {
        if (root.danger) return Theme.error
        if (root.success) return Theme.success
        if (root.secondary) return Theme.secondary
        if (Theme.buttonStyle === "outline") return "transparent"
        if (Theme.buttonStyle === "soft") return Theme.accent
        return Theme.primary
    }

    onClicked: App.bumpIdle()
}
