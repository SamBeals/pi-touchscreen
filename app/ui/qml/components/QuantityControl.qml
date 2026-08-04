import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    spacing: Theme.gap
    property int quantity: 1

    signal decrement()
    signal increment()

    SecondaryButton {
        text: "−"
        Layout.fillWidth: true
        onClicked: root.decrement()
    }
    Text {
        text: "Qty: " + root.quantity
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true
    }
    SecondaryButton {
        text: "+"
        Layout.fillWidth: true
        onClicked: root.increment()
    }
}
