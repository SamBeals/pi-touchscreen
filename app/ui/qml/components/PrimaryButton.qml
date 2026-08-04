import QtQuick
import QtQuick.Controls
import SellMate 1.0

Button {
    id: root
    property bool danger: false
    property bool success: false
    property bool secondary: false

    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodyFontPx + 2
    font.bold: true
    implicitHeight: Math.max(
        root.secondary ? Theme.secondaryButtonMinHeight : Theme.primaryButtonMinHeight,
        implicitContentHeight + 28
    )
    leftPadding: 32
    rightPadding: 32
    topPadding: 18
    bottomPadding: 18

    background: Item {
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: root.down ? 2 : 0
            radius: Theme.buttonShape === "pill" ? height / 2
                  : Theme.buttonShape === "square" ? Theme.squareRadius
                  : Theme.cornerRadius
            color: {
                if (!root.enabled) return Theme.border
                if (root.down) return Qt.darker(_fill(), 1.08)
                return _fill()
            }
            border.width: Theme.buttonStyle === "outline" || root.secondary ? 1 : 0
            border.color: root.danger ? Theme.error : (root.secondary ? Theme.border : Theme.primary)

            // Soft lift for primary filled buttons
            Rectangle {
                visible: !root.secondary && Theme.buttonStyle === "filled" && root.enabled && !root.danger
                anchors.fill: parent
                anchors.margins: -1
                anchors.topMargin: 2
                z: -1
                radius: parent.radius
                color: Theme.shadowLift
            }
        }
    }

    contentItem: Text {
        text: root.text
        font: root.font
        color: _labelColor()
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }

    function _fill() {
        if (root.danger) return Theme.error
        if (root.success) return Theme.success
        if (root.secondary) return Theme.secondary
        if (Theme.buttonStyle === "outline") return "transparent"
        if (Theme.buttonStyle === "soft") return Theme.secondary
        return Theme.primary
    }

    function _labelColor() {
        if (!root.enabled) return Theme.textMuted
        if (Theme.buttonStyle === "outline")
            return root.danger ? Theme.error : Theme.text
        if (root.secondary) return Theme.text
        if (root.danger) return Theme.onContrast
        if (root.success) return Theme.onContrast
        // Lime primary reads best with charcoal labels
        return Theme.mode === "light" ? Theme.text : Theme.onContrast
    }

    onClicked: App.bumpIdle()

    Behavior on scale {
        NumberAnimation { duration: Theme.animationMs; easing.type: Easing.OutCubic }
    }
    scale: down ? 0.98 : 1.0
}
