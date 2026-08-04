import QtQuick
import QtQuick.Layouts

ColumnLayout {
    property string message: ""
    spacing: Theme.sectionGap
    Layout.fillWidth: true

    Item { Layout.fillHeight: true; Layout.preferredHeight: 1 }

    Text {
        text: "Purchase complete"
        color: Theme.success
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true
    }

    Text {
        text: message
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true
    }

    Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

    PrimaryButton {
        text: "Done"
        success: true
        Layout.fillWidth: true
        onClicked: App.finishToAttract()
    }
}
